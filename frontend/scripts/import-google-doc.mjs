#!/usr/bin/env node
// Import a Google Doc into /docs as an MDX page, keeping its headings, formatting, lists, tables,
// links and images. Images are downloaded into public/docs-assets/<slug>/ so the page never
// depends on Google's image URLs.
//
//   npm run docs:import -- <google-doc-link> [--slug name] [--title "Title"] [--force]
//
// Public docs ("Anyone with the link can view") need nothing else. For a private doc, set
// GOOGLE_ACCESS_TOKEN to an OAuth token with Drive read access (for example
// `gcloud auth print-access-token --scopes=https://www.googleapis.com/auth/drive.readonly`).
// `--html <file>` converts a saved "Download > Web page (.html)" export instead of fetching.
import { mkdir, readFile, writeFile, access, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { unified } from "unified";
import rehypeParse from "rehype-parse";
import rehypeRemark from "rehype-remark";
import remarkGfm from "remark-gfm";
import remarkStringify from "remark-stringify";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DOCS_DIR = path.join(ROOT, "content", "docs");
const ASSETS_DIR = path.join(ROOT, "public", "docs-assets");
const SECTION = "---Imported from Google Docs---";
const IMAGE_TYPES = { "image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp", "image/svg+xml": "svg" };

export function docIdFrom(input) {
  const match = /\/document\/(?:u\/\d+\/)?d\/([a-zA-Z0-9_-]{20,})/.exec(input) ?? /^([a-zA-Z0-9_-]{20,})$/.exec(input.trim());
  if (!match) throw new Error("That is not a Google Docs link. Expected https://docs.google.com/document/d/<id>/...");
  return match[1];
}

export function slugify(text) {
  return text.toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9\s-]/g, "")
    .trim().replace(/[\s-]+/g, "-").replace(/^-|-$/g, "").slice(0, 80);
}

// ---------- hast helpers ----------
const el = (tagName, children = [], properties = {}) => ({ type: "element", tagName, properties, children });
const txt = (value) => ({ type: "text", value });
const classes = (node) => [].concat(node.properties?.className ?? []).map(String);
function textOf(node) {
  if (node.type === "text") return node.value;
  return (node.children ?? []).map(textOf).join("");
}
function walk(node, visit, parent = null) {
  visit(node, parent);
  for (const child of [...(node.children ?? [])]) walk(child, visit, node);
}
function find(node, test) {
  if (test(node)) return node;
  for (const child of node.children ?? []) { const hit = find(child, test); if (hit) return hit; }
  return null;
}

// Google Docs puts all inline formatting in generated CSS classes (.c3{font-weight:700}).
function classStyles(css) {
  const styles = new Map();
  for (const [, selectors, body] of css.matchAll(/([^{}]+)\{([^}]*)\}/g)) {
    const flags = {
      bold: /font-weight:\s*(700|800|900|bold)/.test(body),
      italic: /font-style:\s*italic/.test(body),
      strike: /text-decoration[^;]*line-through/.test(body),
      mono: /font-family:[^;]*(courier|consolas|mono|source code|menlo|inconsolata)/i.test(body),
    };
    for (const selector of selectors.split(",")) {
      const name = /^\s*\.([\w-]+)\s*$/.exec(selector)?.[1];
      if (name) styles.set(name, { ...(styles.get(name) ?? {}), ...Object.fromEntries(Object.entries(flags).filter(([, v]) => v)) });
    }
  }
  return styles;
}

function unwrapGoogleLink(href) {
  try {
    const url = new URL(href);
    if (/(^|\.)google\.com$/.test(url.hostname) && url.pathname === "/url" && url.searchParams.get("q")) return url.searchParams.get("q");
  } catch {}
  return href;
}

// Wrap a span's content in strong/em/del/code, keeping edge whitespace outside the markers.
function formatSpan(span, flags) {
  if (!flags.bold && !flags.italic && !flags.strike && !flags.mono) return span.children;
  const onlyText = span.children.every(c => c.type === "text");
  const raw = onlyText ? textOf(span) : null;
  if (onlyText && !raw.trim()) return span.children;
  let lead = "", trail = "", inner = span.children;
  if (onlyText) {
    lead = /^\s*/.exec(raw)[0]; trail = /\s*$/.exec(raw)[0];
    inner = [txt(raw.slice(lead.length, raw.length - trail.length))];
  }
  let node = flags.mono && onlyText ? el("code", inner) : null;
  for (const [flag, tag] of [["strike", "del"], ["italic", "em"], ["bold", "strong"]]) {
    if (flags[flag]) node = el(tag, node ? [node] : inner);
  }
  return [...(lead ? [txt(lead)] : []), node ?? el("span", inner), ...(trail ? [txt(trail)] : [])];
}

const listLevel = (node) => {
  if (node.type !== "element" || !["ul", "ol"].includes(node.tagName)) return null;
  const level = classes(node).map(c => /^lst-kix_[\w]+-(\d+)$/.exec(c)?.[1]).find(Boolean);
  return level === undefined ? 0 : Number(level);
};

// Google exports nested lists as flat sibling lists tagged with a level; rebuild the nesting.
function nestLists(parent) {
  const out = [];
  let stack = [];
  for (const node of parent.children) {
    const level = listLevel(node);
    if (level === null) {
      if (stack.length && node.type === "text" && !node.value.trim()) continue;
      stack = []; out.push(node); continue;
    }
    const items = node.children.filter(c => c.type === "element" && c.tagName === "li");
    while (stack.length && stack.at(-1).level > level) stack.pop();
    const top = stack.at(-1);
    if (top && top.level === level && top.list.tagName === node.tagName) { top.list.children.push(...items); continue; }
    if (top && top.level === level) stack.pop();
    const list = el(node.tagName, items);
    const owner = stack.at(-1);
    const lastItem = owner?.list.children.at(-1);
    if (owner && lastItem) lastItem.children.push(list); else out.push(list);
    stack.push({ level, list });
  }
  parent.children = out;
}

const LANGUAGES = /^(sql|python|py|bash|sh|shell|powershell|js|javascript|ts|typescript|jsx|tsx|json|yaml|yml|toml|html|css|go|rust|java|kotlin|c|cpp|c\+\+|c#|csharp|ruby|php|swift|text|plain text|markdown|md|dockerfile|ini|xml)$/i;
const fenceLanguage = (label) => label.toLowerCase().replace("plain text", "text").replace("c++", "cpp").replace("c#", "csharp");
const codeElement = (lines, lang) => el("pre", [el("code", [txt(lines.join("\n"))], lang ? { className: [`language-${fenceLanguage(lang)}`] } : {})]);

// Code blocks, from three shapes a Google Doc can hold:
//  - a run of paragraphs set entirely in a monospace font (also Docs' own code block, with its
//    language label on the line above),
//  - Markdown fences typed as plain text (``` … ```).
function codeBlocks(parent) {
  const out = [];
  let run = [];
  const isP = (n) => n.type === "element" && n.tagName === "p";
  const isCodeLine = (n) => isP(n) && n.children.length > 0 &&
    n.children.every(c => (c.type === "element" && c.tagName === "code") || (c.type === "text" && !c.value.trim())) &&
    n.children.some(c => c.type === "element");
  const flush = () => {
    if (!run.length) return;
    const prev = out.findLastIndex(n => n.type === "element");
    const label = prev >= 0 && isP(out[prev]) ? textOf(out[prev]).trim() : "";
    const lang = LANGUAGES.test(label) ? label : "";
    if (lang) out.splice(prev, 1);
    out.push(codeElement(run.map(textOf), lang));
    run = [];
  };
  const children = parent.children;
  for (let i = 0; i < children.length; i++) {
    const node = children[i];
    const fence = isP(node) ? /^```\s*([\w+#-]*)\s*$/.exec(textOf(node).trim()) : null;
    const close = fence ? children.slice(i + 1).findIndex(n => isP(n) && textOf(n).trim() === "```") : -1;
    if (fence && close >= 0) {
      flush();
      out.push(codeElement(children.slice(i + 1, i + 1 + close).filter(isP).map(textOf), fence[1]));
      i += close + 1;
      continue;
    }
    if (run.length && node.type === "text" && !node.value.trim()) continue;
    if (isCodeLine(node)) run.push(node); else { flush(); out.push(node); }
  }
  flush();
  parent.children = out;
}

/**
 * Convert Google Docs HTML export to MDX.
 * `saveImage(src, index)` stores one image and returns its public URL path.
 */
export async function convertGoogleDocHtml(html, { saveImage, title: forcedTitle } = {}) {
  const tree = unified().use(rehypeParse).parse(html);
  const css = [];
  walk(tree, (node) => { if (node.type === "element" && node.tagName === "style") css.push(textOf(node)); });
  const styles = classStyles(css.join("\n"));
  const body = find(tree, n => n.type === "element" && n.tagName === "body") ?? tree;

  // Title and subtitle paragraphs become frontmatter, not body text.
  let title = forcedTitle ?? "", description = "";
  const titleNode = find(body, n => n.type === "element" && classes(n).includes("title"));
  const subtitleNode = find(body, n => n.type === "element" && classes(n).includes("subtitle"));
  if (titleNode) { title ||= textOf(titleNode).trim(); titleNode.tagName = "x-drop"; }
  if (subtitleNode) { description = textOf(subtitleNode).trim(); subtitleNode.tagName = "x-drop"; }
  const headTitle = find(tree, n => n.type === "element" && n.tagName === "title");
  if (!title && headTitle) title = textOf(headTitle).trim();
  if (!title) { const h = find(body, n => n.type === "element" && /^h[1-6]$/.test(n.tagName)); if (h) title = textOf(h).trim(); }
  title ||= "Imported document";

  // Comments are exported as [a] markers plus a trailing block; neither belongs on the page.
  walk(body, (node, parent) => {
    if (node.type !== "element" || !parent) return;
    const isComment = (n) => n.type === "element" && n.tagName === "a" && /^#?cmnt(_ref)?\d+$/.test(String(n.properties?.href ?? n.properties?.id ?? ""));
    if ((node.tagName === "sup" && node.children.some(isComment)) || (node.tagName === "div" && find(node, isComment))) node.tagName = "x-drop";
  });

  // Headings: the page title is the only h1, so shift the doc's headings down when it uses h1.
  const headings = [];
  walk(body, (node) => { if (node.type === "element" && /^h[1-6]$/.test(node.tagName)) headings.push(node); });
  const shift = headings.some(h => h.tagName === "h1") ? 1 : 0;
  const slugs = new Map(), used = new Map();
  for (const h of headings) {
    h.tagName = `h${Math.min(6, Number(h.tagName[1]) + shift)}`;
    const base = slugify(textOf(h)) || "section";
    const count = used.get(base) ?? 0; used.set(base, count + 1);
    if (h.properties?.id) slugs.set(String(h.properties.id), count ? `${base}-${count}` : base);
    for (const child of h.children) if (child.type === "element" && child.tagName === "a" && child.properties?.id && !child.properties.href) slugs.set(String(child.properties.id), count ? `${base}-${count}` : base);
  }

  // Inline formatting, links, and images.
  const images = [];
  const rewrite = (parent) => {
    const next = [];
    for (const node of parent.children ?? []) {
      if (node.type === "comment" || (node.type === "element" && ["x-drop", "style", "script", "meta", "title"].includes(node.tagName))) continue;
      // Docs marks its code blocks with private-use characters (U+EC03 …) that render as boxes.
      if (node.type === "text") { next.push(txt(node.value.replace(/ /g, " ").replace(/[-]/g, ""))); continue; }
      if (node.type !== "element") { next.push(node); continue; }
      rewrite(node);
      if (node.tagName === "span") {
        const flags = classes(node).reduce((f, c) => ({ ...f, ...(styles.get(c) ?? {}) }), {});
        next.push(...formatSpan(node, flags));
        continue;
      }
      if (node.tagName === "a") {
        const href = node.properties?.href ? unwrapGoogleLink(String(node.properties.href)) : "";
        // Bookmark anchors, and links with no visible text (Docs leaves these around edited links).
        if (!href || (!textOf(node).trim() && !find(node, n => n.type === "element" && n.tagName === "img"))) { next.push(...node.children); continue; }
        if (href.startsWith("#")) {
          const target = slugs.get(href.slice(1));
          if (!target) { next.push(...node.children); continue; } // footnote/comment jumps have no target on the page
          node.properties = { href: `#${target}` };
        } else node.properties = { href };
        next.push(node); continue;
      }
      if (node.tagName === "img") {
        const src = String(node.properties?.src ?? "");
        if (!src) continue;
        const alt = String(node.properties?.alt ?? node.properties?.title ?? "").trim();
        node.properties = { src, alt };
        images.push(node);
        next.push(node); continue;
      }
      if (node.tagName === "table") {
        // Docs tables have no header cells; Markdown tables need one, so the first row becomes it.
        const firstRow = find(node, n => n.type === "element" && n.tagName === "tr");
        if (firstRow && !firstRow.children.some(c => c.type === "element" && c.tagName === "th")) {
          for (const cell of firstRow.children) if (cell.type === "element" && cell.tagName === "td") cell.tagName = "th";
        }
      }
      if (["p", "li"].includes(node.tagName) && !textOf(node).trim() && !find(node, n => n.type === "element" && ["img", "ul", "ol"].includes(n.tagName))) continue;
      if (/^h[1-6]$/.test(node.tagName)) {
        // Headings are already bold; Docs' bold class on them would print as ## **Title**.
        const plain = (n) => n.type === "element" && ["strong", "em"].includes(n.tagName) ? n.children.flatMap(plain) : [n];
        node.children = node.children.flatMap(plain);
      }
      next.push(node);
    }
    parent.children = next;
  };
  rewrite(body);
  // A first heading that repeats the page title would show the title twice.
  // Docs often wraps the opening in an empty <div>, so look for the first block anywhere.
  const firstBlock = find(body, n => n.type === "element" && (/^h[1-6]$/.test(n.tagName) || ["p", "li", "table", "img"].includes(n.tagName)));
  const same = (a, b) => a.replace(/\s+/g, " ").trim().toLowerCase() === b.replace(/\s+/g, " ").trim().toLowerCase();
  if (firstBlock && /^h[1-6]$/.test(firstBlock.tagName) && same(textOf(firstBlock), title)) {
    walk(body, (node, parent) => { if (node === firstBlock) parent.children.splice(parent.children.indexOf(node), 1); });
  }
  walk(body, (node) => {
    if (node.type !== "element" || !node.children?.length) return;
    nestLists(node);
    // Table cells keep inline code; a fenced block inside a Markdown table row breaks the table.
    if (!["td", "th"].includes(node.tagName)) codeBlocks(node);
  });

  const saved = new Map();
  for (const [index, img] of images.entries()) {
    const src = img.properties.src;
    if (!saved.has(src)) saved.set(src, saveImage ? await saveImage(src, saved.size + 1) : src);
    img.properties.src = saved.get(src);
    if (!img.properties.alt) img.properties.alt = `${title} image ${index + 1}`;
  }

  const mdast = await unified().use(rehypeRemark).run(tree);
  const markdown = unified().use(remarkGfm).use(remarkStringify, {
    bullet: "-", emphasis: "_", rule: "-", fences: true,
    // MDX treats { } as expressions and < as JSX; escape them in prose.
    unsafe: [{ character: "{", inConstruct: "phrasing" }, { character: "}", inConstruct: "phrasing" }, { character: "<", inConstruct: "phrasing" }],
  }).stringify(mdast);
  return { title, description, markdown: markdown.trim() + "\n", images: saved.size };
}

// ---------- CLI ----------
async function fetchDocHtml(id) {
  const token = process.env.GOOGLE_ACCESS_TOKEN;
  const url = token ? `https://www.googleapis.com/drive/v3/files/${id}/export?mimeType=text%2Fhtml` : `https://docs.google.com/document/d/${id}/export?format=html`;
  const response = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {}, redirect: "follow" });
  if (!token && /accounts\.google\.com|ServiceLogin/.test(response.url)) throw new Error("This doc is private. Share it as \"Anyone with the link can view\", or set GOOGLE_ACCESS_TOKEN (see the top of this script).");
  if (response.status === 401 || response.status === 403) throw new Error(token ? "Google rejected GOOGLE_ACCESS_TOKEN, or it cannot read this doc." : "Google refused access. Share the doc as \"Anyone with the link can view\".");
  if (response.status === 404) throw new Error("Google Docs could not find that document.");
  if (!response.ok) throw new Error(`Google Docs export failed with HTTP ${response.status}.`);
  const html = await response.text();
  if (!/<body/i.test(html)) throw new Error("Google Docs did not return an HTML export.");
  let title = "";
  if (token) {
    const meta = await fetch(`https://www.googleapis.com/drive/v3/files/${id}?fields=name`, { headers: { Authorization: `Bearer ${token}` } });
    if (meta.ok) title = (await meta.json()).name ?? "";
  }
  return { html, title };
}

const MAX_IMAGE_WIDTH = 1600;
let sharpModule;
// sharp ships with Next.js; without it, images are saved exactly as Google serves them.
async function loadSharp() {
  if (sharpModule === undefined) sharpModule = await import("sharp").then(m => m.default, () => null);
  return sharpModule;
}

async function downloadImage(src, dir, publicPath, index) {
  let bytes, type;
  const data = /^data:([^;,]+);base64,(.*)$/s.exec(src);
  if (data) { type = data[1]; bytes = Buffer.from(data[2], "base64"); }
  else {
    if (!/^https?:\/\//.test(src)) throw new Error(`Unsupported image source: ${src.slice(0, 80)}`);
    const response = await fetch(src, { redirect: "follow" });
    if (!response.ok) throw new Error(`Image ${index} download failed with HTTP ${response.status}.`);
    type = (response.headers.get("content-type") ?? "").split(";")[0].trim();
    bytes = Buffer.from(await response.arrayBuffer());
  }
  let ext = IMAGE_TYPES[type];
  if (!ext) throw new Error(`Image ${index} is not a supported image type (${type || "unknown"}).`);
  if (bytes.length > 15 * 1024 * 1024) throw new Error(`Image ${index} is larger than 15 MB.`);
  // Screenshots exported from Docs are often several MB. Re-encode as WebP, capped at the docs
  // column's useful width; keep the original when that isn't smaller. GIFs (animation) and SVGs stay.
  if (["png", "jpg", "webp"].includes(ext)) {
    const sharp = await loadSharp();
    if (sharp) {
      const webp = await sharp(bytes).rotate().resize({ width: MAX_IMAGE_WIDTH, withoutEnlargement: true }).webp({ quality: 82, effort: 5 }).toBuffer();
      if (webp.length < bytes.length) { bytes = webp; ext = "webp"; }
    }
  }
  const name = `image-${String(index).padStart(2, "0")}.${ext}`;
  await writeFile(path.join(dir, name), bytes);
  return `${publicPath}/${name}`;
}

function parseArgs(argv) {
  const args = { force: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--force") args.force = true;
    else if (["--slug", "--title", "--html"].includes(a)) args[a.slice(2)] = argv[++i];
    else if (!a.startsWith("--") && !args.source) args.source = a;
    else throw new Error(`Unknown option: ${a}`);
  }
  if (!args.source && !args.html) throw new Error("Usage: npm run docs:import -- <google-doc-link> [--slug name] [--title \"Title\"] [--force]");
  return args;
}

const exists = (p) => access(p).then(() => true, () => false);

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const id = args.source ? docIdFrom(args.source) : null;
  const fetched = args.html ? { html: await readFile(args.html, "utf8"), title: "" } : await fetchDocHtml(id);
  // Convert once without images to learn the title, which decides the slug and image folder.
  const preview = await convertGoogleDocHtml(fetched.html, { title: args.title || fetched.title || undefined });
  const slug = args.slug ?? slugify(preview.title);
  if (!/^[a-z0-9][a-z0-9-]{0,79}$/.test(slug)) throw new Error(`"${slug}" is not a valid page slug. Pass --slug with lowercase letters, numbers and dashes.`);
  const file = path.join(DOCS_DIR, `${slug}.mdx`);
  if (!args.force && await exists(file)) throw new Error(`content/docs/${slug}.mdx already exists. Pass --force to replace it, or --slug for a new page.`);

  const imageDir = path.join(ASSETS_DIR, slug);
  // A refresh replaces the page's images, so files from the previous import don't linger.
  await rm(imageDir, { recursive: true, force: true });
  await mkdir(imageDir, { recursive: true });
  const result = await convertGoogleDocHtml(fetched.html, {
    title: args.title || fetched.title || undefined,
    saveImage: (src, index) => downloadImage(src, imageDir, `/docs-assets/${slug}`, index),
  });
  const source = id ? `https://docs.google.com/document/d/${id}` : path.basename(args.html);
  // The source note is a YAML comment: an MDX {/* */} comment here breaks fumadocs' build.
  const frontmatter = `---\n# Imported from Google Docs: ${source} on ${new Date().toISOString().slice(0, 10)}.\n# Refresh with: npm run docs:import -- <link> --slug ${slug} --force\n` +
    `title: ${JSON.stringify(result.title)}\ndescription: ${JSON.stringify(result.description || "Imported from Google Docs.")}\n---\n\n`;
  await writeFile(file, frontmatter + result.markdown);

  const metaFile = path.join(DOCS_DIR, "meta.json");
  const meta = JSON.parse(await readFile(metaFile, "utf8"));
  if (!meta.pages.includes(slug)) {
    if (!meta.pages.includes(SECTION)) meta.pages.push(SECTION);
    meta.pages.push(slug);
    await writeFile(metaFile, JSON.stringify(meta, null, 2) + "\n");
  }
  console.log(`Imported "${result.title}" → content/docs/${slug}.mdx (${result.images} image${result.images === 1 ? "" : "s"} in public/docs-assets/${slug}/). Open /docs/${slug}.`);
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  main().catch((error) => { console.error(`docs:import failed: ${error.message}`); process.exit(1); });
}
