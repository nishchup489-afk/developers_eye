// Isolated browser preview of the real search/overview routes. Uses fake credentials
// and intercepts only the two fixture upstreams inside a child Next process.
import { spawn } from "node:child_process";
import { resolve } from "node:path";

if (process.env.EYE_OVERVIEW_PREVIEW_CHILD === "1") {
  const original = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    const request = new Request(input, init);
    const url = new URL(request.url);
    if (url.hostname === "overview-preview.test") {
      if (url.pathname.endsWith("/suggest")) return Response.json({ suggested_query: url.searchParams.get("q"), corrections: [] });
      return Response.json({ results: [
        { title: "Coroutines and Tasks — Python documentation", source: "docs", url: "https://docs.python.org/3/library/asyncio-task.html", snippet: "Coroutines declared with the async/await syntax are the preferred way of writing asyncio applications. The asyncio.create_task() function schedules coroutines to run concurrently.", score: 4 },
        { title: "Concurrency and async / await — FastAPI", source: "docs", url: "https://fastapi.tiangolo.com/async/", snippet: "Use async def when working with libraries that support await. Concurrent code can wait for network and file operations while serving other requests.", score: 3 },
        { title: "asyncio — Asynchronous I/O", source: "docs", url: "https://docs.python.org/3/library/asyncio.html", snippet: "asyncio is a library to write concurrent code using the async/await syntax. It is often a good fit for IO-bound and high-level structured network code.", score: 2 },
      ] });
    }
    if (url.hostname === "api.groq.com") {
      if (process.env.EYE_OVERVIEW_PREVIEW_ERROR === "1") return Response.json({}, { status: 429, headers: { "Retry-After": "60" } });
      return Response.json({ choices: [{ finish_reason: "stop", message: { content: JSON.stringify({ paragraphs: [
        { text: "Python’s async/await syntax lets you write concurrent code with asyncio. It is a good fit for I/O-bound work such as network requests, where tasks can wait without holding up other work.", sources: [1, 3] },
        { text: "Declare a coroutine with async def, then use await with libraries that support it. To run coroutines concurrently, asyncio.create_task() schedules them as tasks.", sources: [1, 2] },
        { text: "In FastAPI, async def is useful when your underlying libraries support await. Choose that approach based on the I/O library you are using.", sources: [2] },
      ] }) } }] });
    }
    return original(input, init);
  };
} else {
  const child = spawn(process.execPath, ["--import", import.meta.url, "node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "--port", "3456"], {
    cwd: resolve(import.meta.dirname, ".."), stdio: "inherit", env: { ...process.env,
      NEXT_BUILD_DIR: process.env.NEXT_BUILD_DIR || ".next-ai-overview", EYE_OVERVIEW_PREVIEW_CHILD: "1",
      BACKEND_URL: "http://overview-preview.test", GROQ_API_KEY: "fake-preview-key", AI_OVERVIEW: "on", KNOWLEDGE_PANEL: "off",
    },
  });
  process.on("SIGINT", () => { child.kill(); process.exit(0); });
  process.on("SIGTERM", () => { child.kill(); process.exit(0); });
  child.on("exit", (code) => process.exit(code ?? 0));
}
