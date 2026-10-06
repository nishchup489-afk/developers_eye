import type { SearchResult } from "./search";

// Curated fixtures only. These are never presented as live search results.
export const demoResults: SearchResult[] = [
  { title: "Concurrency and async / await", source: "docs", url: "https://fastapi.tiangolo.com/async/", snippet: "Understand asynchronous code, concurrency, and parallelism. Learn when to use async def in your FastAPI path operations.", score: 14.82, tags: ["python", "fastapi", "async"] },
  { title: "FastAPI — high performance, easy to learn", source: "github", url: "https://github.com/fastapi/fastapi", snippet: "A modern Python web framework for building APIs with standard type hints. Explore the implementation, examples, and community discussions.", score: 12.64, tags: ["python", "fastapi", "backend"] },
  { title: "Asynchronous I/O with Python asyncio", source: "docs", url: "https://docs.python.org/3/library/asyncio.html", snippet: "Write concurrent Python code using the async/await syntax. A foundation for asynchronous frameworks, network services, and database connections.", score: 11.21, tags: ["python", "async", "backend"] },
  { title: "FastAPI questions, answered by developers", source: "stackoverflow", url: "https://stackoverflow.com/questions/tagged/fastapi", snippet: "Explore community questions on FastAPI, async database sessions, dependency injection, and production API development.", score: 10.32, tags: ["fastapi", "python", "database"] },
  { title: "The Python community", source: "reddit", url: "https://www.reddit.com/r/Python/", snippet: "Discover Python projects, engineering experiences, and discussions from the community. A starting point for a different perspective.", score: 8.47, tags: ["python", "community"] },
  { title: "FastAPI stories from the DEV community", source: "articles", url: "https://dev.to/t/fastapi", snippet: "Tutorials and developer perspectives on building Python APIs, authentication, background tasks, and backend services.", score: 8.12, tags: ["fastapi", "python", "tutorial"] },
  { title: "Thinking in React", source: "docs", url: "https://react.dev/learn/thinking-in-react", snippet: "Break a user interface into components, describe its visual states, and connect components so that data flows through them.", score: 13.1, tags: ["react", "frontend", "javascript"] },
  { title: "Next.js: the React framework for the web", source: "github", url: "https://github.com/vercel/next.js", snippet: "Explore the source of Next.js, including routing, server rendering, caching, and the React framework's architecture.", score: 12.2, tags: ["nextjs", "react", "frontend"] },
  { title: "Redis data types", source: "docs", url: "https://redis.io/docs/latest/develop/data-types/", snippet: "Learn the core data structures behind caching, queues, and real-time applications, from strings and hashes to streams.", score: 12.7, tags: ["redis", "caching", "backend"] },
  { title: "SQLAlchemy asynchronous I/O", source: "docs", url: "https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html", snippet: "Use async engines and sessions to connect your Python applications to a database with SQLAlchemy.", score: 11.8, tags: ["python", "sqlalchemy", "async", "database"] },
  { title: "Binary search", source: "practice", url: "https://leetcode.com/problems/binary-search/", snippet: "Practice searching a sorted array in logarithmic time. Build an intuition for search boundaries and algorithm complexity.", score: 10.9, tags: ["algorithms", "binary", "search", "leetcode"] },
  { title: "Python community events", source: "events", url: "https://www.python.org/events/", snippet: "Find Python conferences, meetups, and community events around the world. Visit the source for current dates and locations.", score: 9.5, tags: ["python", "events", "conference", "meetup"] },
];

export function searchDemo(query: string, source?: string): SearchResult[] {
  const terms = query.toLowerCase().split(/\W+/).filter(Boolean);
  return demoResults.map(result => {
    const text = `${result.title} ${result.snippet} ${result.tags?.join(" ")}`.toLowerCase();
    const matches = terms.filter(term => text.includes(term)).length;
    return { result, matches };
  }).filter(({ result, matches }) => matches > 0 && (!source || result.source === source))
    .sort((a, b) => b.matches - a.matches || b.result.score - a.result.score)
    .map(({ result }) => result);
}
