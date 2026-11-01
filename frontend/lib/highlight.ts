// A small, dependency-free highlighter for code pasted into the search bar.
// It only needs to look right in a preview, not to parse every language.

export type TokenType =
  | "comment"
  | "string"
  | "decorator"
  | "keyword"
  | "literal"
  | "type"
  | "function"
  | "plain";
export type Token = { type: TokenType; text: string };

type Language = {
  name: string;
  test: RegExp[];
  comment: RegExp;
  keywords: string[];
};

const cKeywords =
  "if else for while do switch case break continue return new delete try catch finally throw class extends import export from default const let var function async await yield typeof instanceof in of this super static public private protected void interface type enum implements as";

const languages: Language[] = [
  {
    name: "Python",
    test: [
      /^\s*(def|class)\s+\w+.*:\s*$/m,
      /^\s*(from\s+[\w.]+\s+)?import\s+\w+/m,
      /^\s*@\w+/m,
      /\b(elif|self|None|True|False)\b/,
    ],
    comment: /#.*/y,
    keywords:
      "def class return if elif else for while in not and or is import from as with try except finally raise pass break continue lambda yield async await global nonlocal assert del".split(" "),
  },
  {
    name: "TypeScript",
    test: [/\binterface\s+\w+/, /:\s*(string|number|boolean)\b/, /\btype\s+\w+\s*=/],
    comment: /\/\/.*|\/\*[\s\S]*?\*\//y,
    keywords: cKeywords.split(" "),
  },
  {
    name: "JavaScript",
    test: [/\b(const|let|var)\s+\w+\s*=/, /=>/, /\bfunction\s*\w*\s*\(/, /console\.\w+/],
    comment: /\/\/.*|\/\*[\s\S]*?\*\//y,
    keywords: cKeywords.split(" "),
  },
  {
    name: "Go",
    test: [/^package\s+\w+/m, /\bfunc\s+(\(\w+\s+\*?\w+\)\s*)?\w+\(/, /:=/],
    comment: /\/\/.*|\/\*[\s\S]*?\*\//y,
    keywords:
      "package import func return if else for range switch case default break continue go defer chan map struct interface type var const select".split(" "),
  },
  {
    name: "Rust",
    test: [/\bfn\s+\w+\s*\(/, /\blet\s+mut\b/, /\bimpl\b/, /println!/],
    comment: /\/\/.*|\/\*[\s\S]*?\*\//y,
    keywords:
      "fn let mut pub struct enum impl trait use mod return if else match for while loop in break continue as where self Self crate async await move ref const static".split(" "),
  },
  {
    name: "Java",
    test: [/\bpublic\s+(static\s+)?(class|void)\b/, /System\.out\./],
    comment: /\/\/.*|\/\*[\s\S]*?\*\//y,
    keywords: (cKeywords + " package final abstract throws synchronized").split(" "),
  },
  {
    name: "SQL",
    test: [/\bselect\b[\s\S]+\bfrom\b/i, /\b(insert\s+into|create\s+table|update\s+\w+\s+set)\b/i],
    comment: /--.*/y,
    keywords:
      "select from where join left right inner outer on group by order having limit insert into values update set delete create table index and or not null as distinct union".split(" "),
  },
  {
    name: "Bash",
    test: [/^#!.*sh/m, /^\s*(sudo|npm|pip|git|cd|echo|export)\s/m],
    comment: /#.*/y,
    keywords: "if then else fi for in do done while case esac function export local return".split(" "),
  },
];

const fallback: Language = {
  name: "Code",
  test: [],
  comment: /\/\/.*|#.*/y,
  keywords: [],
};

/** Picks the language whose hints match the most, or a generic one. */
export function detectLanguage(code: string): Language {
  let best = fallback;
  let bestScore = 0;
  for (const language of languages) {
    const score = language.test.filter((re) => re.test(code)).length;
    if (score > bestScore) [best, bestScore] = [language, score];
  }
  return best;
}

const literals = new Set(
  "True False None true false null undefined nil NaN".split(" "),
);
const builtinTypes = new Set(
  "int float str bool list dict set tuple bytes object string number boolean any unknown never void i32 i64 u32 u64 f64 usize String Vec Option Result".split(" "),
);
const string = /"""[\s\S]*?"""|'''[\s\S]*?'''|`(?:\\[\s\S]|[^\\`])*`|"(?:\\.|[^\\"\n])*"|'(?:\\.|[^\\'\n])*'/y;
const decorator = /@[A-Za-z_][\w.]*/y;
const number = /\b\d[\d_]*(\.\d+)?\b/y;
const word = /[A-Za-z_]\w*/y;

function match(re: RegExp, code: string, at: number) {
  re.lastIndex = at;
  return re.exec(code)?.[0];
}

export function highlight(code: string, language: Language): Token[] {
  const keywords = new Set(language.keywords);
  const sql = language.name === "SQL";
  const tokens: Token[] = [];
  const push = (type: TokenType, text: string) => {
    const last = tokens[tokens.length - 1];
    if (last?.type === type) last.text += text;
    else tokens.push({ type, text });
  };
  let i = 0;
  while (i < code.length) {
    let text: string | undefined;
    if ((text = match(language.comment, code, i))) push("comment", text);
    else if ((text = match(string, code, i))) push("string", text);
    else if ((text = match(decorator, code, i))) push("decorator", text);
    else if ((text = match(number, code, i))) push("literal", text);
    else if ((text = match(word, code, i))) {
      const key = sql ? text.toLowerCase() : text;
      push(
        keywords.has(key)
          ? "keyword"
          : literals.has(text)
            ? "literal"
            : builtinTypes.has(text) || /^[A-Z][a-z]\w*$/.test(text)
              ? "type"
              : /^\s*\(/.test(code.slice(i + text.length, i + text.length + 2))
                ? "function"
                : "plain",
        text,
      );
    } else push("plain", (text = code[i]));
    i += text.length;
  }
  return tokens;
}

/** Splits tokens into lines so each line can be numbered. */
export function toLines(tokens: Token[]): Token[][] {
  const lines: Token[][] = [[]];
  for (const token of tokens) {
    token.text.split("\n").forEach((part, index) => {
      if (index > 0) lines.push([]);
      if (part) lines[lines.length - 1].push({ type: token.type, text: part });
    });
  }
  return lines;
}
