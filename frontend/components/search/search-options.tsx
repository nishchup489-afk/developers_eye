"use client";

export function SearchOptions({ language, pageSize, onChange }: {
  language: string; pageSize: number;
  onChange: (language: string, pageSize: number) => void;
}) {
  return <div className="search-options">
    <label>Language preference <select aria-label="Language preference" value={language}
      onChange={(event) => onChange(event.target.value, pageSize)}>
      <option value="">Any language</option><option value="en">English first</option>
      <option value="pt">Portuguese first</option><option value="ru">Russian first</option>
      {language && !["en", "pt", "ru"].includes(language) && <option value={language}>{language} first</option>}
    </select></label>
    <label>Results per page <select aria-label="Results per page" value={pageSize}
      onChange={(event) => onChange(language, Number(event.target.value))}>
      {[10, 20, 50].map((size) => <option key={size} value={size}>{size}</option>)}
      {![10, 20, 50].includes(pageSize) && <option value={pageSize}>{pageSize}</option>}
    </select></label>
    {language && <small>Other languages remain in the results.</small>}
  </div>;
}

export function SearchPagination({ page, canNext, loading, onPage }: {
  page: number; canNext: boolean; loading: boolean; onPage: (page: number) => void;
}) {
  return <nav className="search-pagination" aria-label="Search result pages">
    <button disabled={loading || page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
    <span aria-current="page">Page {page}</span>
    <button disabled={loading || !canNext} onClick={() => onPage(page + 1)}>Next</button>
  </nav>;
}
