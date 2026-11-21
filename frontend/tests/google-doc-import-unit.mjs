// Offline checks for the Google Docs → MDX importer, using HTML shaped like a real Docs export.
import assert from "node:assert/strict";
import { convertGoogleDocHtml, docIdFrom, slugify } from "../scripts/import-google-doc.mjs";

const html = `<html><head><meta content="text/html; charset=UTF-8"><style type="text/css">
ol.lst-kix_a1-0{list-style-type:none}.c1{font-weight:700}.c2{font-style:italic}.c3{font-family:"Courier New";font-weight:400}
.c4{text-decoration:line-through}.title{font-size:26pt}.subtitle{font-size:15pt}.c9{color:#000000}
</style></head><body class="c9">
<p class="title"><span>Crawler Runbook</span></p>
<p class="subtitle"><span>How to run {and stop} the crawler</span></p>
<p class="c9"><span></span></p>
<h1 id="h.abc"><span>Start&nbsp;here</span></h1>
<p><span>Plain </span><span class="c1">bold </span><span class="c2">italic</span><span> and </span><span class="c4">old</span><span> and </span><span class="c3">npm run dev</span><span> &lt;tag&gt;.</span></p>
<p><span>See </span><a href="https://www.google.com/url?q=https://example.com/docs?a%3D1&amp;sa=D&amp;source=editors"><span>the docs</span></a><span> or </span><a href="#h.def"><span>Stop</span></a><span>.</span><sup><a href="#cmnt1" id="cmnt_ref1">[a]</a></sup></p>
<ul class="lst-kix_a1-0 start"><li><span>one</span></li><li><span>two</span></li></ul>
<ul class="lst-kix_a1-1 start"><li><span>two.a</span></li></ul>
<ul class="lst-kix_a1-0"><li><span>three</span></li></ul>
<ol class="lst-kix_b2-0 start" start="1"><li><span>first</span></li><li><span>second</span></li></ol>
<p><span class="c3">const a = 1;</span></p><p><span class="c3">console.log(a);</span></p>
<p><span style="overflow:hidden"><img alt="" src="https://lh7-rt.googleusercontent.com/docsz/abc123" style="width: 100px"></span></p>
<p><span><img alt="Diagram" src="data:image/png;base64,iVBORw0KGgo="></span></p>
<table><tr><td><p><span class="c1">Name</span></p></td><td><p><span>Value</span></p></td></tr><tr><td><p><span>workers</span></p></td><td><p><span>16</span></p></td></tr></table>
<h2 id="h.def"><span>Stop</span></h2>
<p><span>Done.</span></p>
<div><p><a href="#cmnt_ref1" id="cmnt1">[a]</a><span>Reviewer comment</span></p></div>
</body></html>`;

const saved = [];
const result = await convertGoogleDocHtml(html, { saveImage: async (src, i) => { saved.push(src); return `/docs-assets/runbook/image-0${i}.png`; } });
const md = result.markdown;

assert.equal(result.title, "Crawler Runbook");
assert.equal(result.description, "How to run {and stop} the crawler");
assert.equal(result.images, 2);
assert.deepEqual(saved.map(s => s.slice(0, 22)), ["https://lh7-rt.googleu", "data:image/png;base64,"]);
assert.match(md, /^## Start here$/m, "h1 shifted to h2, nbsp normalised");
assert.match(md, /^### Stop$/m);
assert.match(md, /Plain \*\*bold\*\* _italic_ and ~~old~~ and `npm run dev` \\<tag>\./, md);
assert.match(md, /\[the docs\]\(https:\/\/example\.com\/docs\?a=1\)/, "google redirect unwrapped");
assert.match(md, /\[Stop\]\(#stop\)/, "heading link rewritten to slug");
assert.doesNotMatch(md, /\[a\]|Reviewer comment/, "comments removed");
assert.match(md, /- one\n- two\n {2}- two\.a\n- three/, "nested list rebuilt");
assert.match(md, /1\. first\n2\. second/);
assert.match(md, /```\nconst a = 1;\nconsole\.log\(a\);\n```/, "monospace paragraphs become a code block");
assert.match(md, /!\[Crawler Runbook image 1\]\(\/docs-assets\/runbook\/image-01\.png\)/);
assert.match(md, /!\[Diagram\]\(\/docs-assets\/runbook\/image-02\.png\)/);
assert.match(md, /\| \*\*Name\*\* \| Value \|\n\| -+ \| -+ \|\n\| workers +\| 16 +\|/, "table kept");
assert.doesNotMatch(md, /Crawler Runbook\n/, "title not repeated in body");

// Shapes seen in a real doc: bold headings, a heading repeating the title, Docs' native code block
// (U+EC03 marker + language label line), typed ``` fences, empty links, code inside table cells.
const real = await convertGoogleDocHtml(`<html><head><title>Drishti Notes</title><style>.c1{font-weight:700}.c18{font-family:"Roboto Mono"}</style></head><body>
<div><p><span></span></p></div><h2><span class="c1">Drishti Notes</span></h2>
<h3><span class="c1">The </span><span>pipeline</span></h3>
<p><span>sql</span></p>
<p><span>&#60419;</span><span class="c18">SELECT </span><span class="c18">s.id</span></p>
<p><span class="c18">&nbsp; &nbsp;FROM source s</span></p>
<p><span>\`\`\`</span></p><p><span>SELECT 1</span></p><p><span>WHERE a &lt;= 2 {x}</span></p><p><span>\`\`\`</span></p>
<p><span>Code:</span><a href="https://example.com/x"><span> </span></a><a href="https://example.com/x"><span>example</span></a></p>
<ul class="lst-kix_z-0"><li><span>item</span></li><li><span></span></li></ul>
<table><tr><td><p><span>Setting</span></p></td></tr><tr><td><p><span class="c18">--concurrency</span></p></td></tr></table>
</body></html>`);
const rmd = real.markdown;
assert.doesNotMatch(rmd, /^#+ Drishti Notes/m, "heading repeating the title dropped");
assert.match(rmd, /^#+ The pipeline$/m, "no ** inside headings");
assert.match(rmd, /```sql\nSELECT s\.id\n {3}FROM source s\n```/, "Docs code block: marker stripped, label becomes language");
assert.match(rmd, /```\nSELECT 1\nWHERE a <= 2 \{x\}\n```/, "typed fences become a real code block");
assert.match(rmd, /Code: \[example\]\(https:\/\/example\.com\/x\)/, "empty link dropped");
assert.doesNotMatch(rmd, /^-\s*$/m, "empty list item dropped");
assert.match(rmd, /\| `--concurrency` \|/, "code in a table cell stays inline");

assert.equal(docIdFrom("https://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQrStUvWxYz_-12345/edit?tab=t.0"), "1AbCdEfGhIjKlMnOpQrStUvWxYz_-12345");
assert.equal(docIdFrom("https://docs.google.com/document/u/0/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/edit"), "1AbCdEfGhIjKlMnOpQrStUvWxYz");
assert.throws(() => docIdFrom("https://example.com/doc"));
assert.equal(slugify("Crawler Runbook: v2 (Draft)"), "crawler-runbook-v2-draft");

console.log("PASS google docs import: formatting, links, comments, nested lists, code, images, tables, frontmatter");
