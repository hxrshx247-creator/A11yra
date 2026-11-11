export function Landing() {
  return (
    <main id="main" className="landing" tabIndex={-1}>
      <section className="landing-hero">
        <div>
          <h1>Make Word handouts easier to navigate</h1>
          <p>Check a handout for barriers that can make reading with a screen reader harder. Review the findings, approve fixes, and download the repaired document.</p>
          <a className="button-link" href="/upload">Check a document</a>
        </div>
        <svg viewBox="0 0 260 230" className="hero-document" aria-hidden="true" focusable="false">
          <rect x="50" y="31" width="156" height="172" rx="15" fill="#dceaf0" opacity=".4" />
          <rect x="36" y="17" width="156" height="172" rx="15" fill="#fff" />
          <g className="hero-lines" fill="none" stroke="#234d68" strokeWidth="7" strokeLinecap="round">
            <path d="M61 55h92M61 77h54" />
            <path d="M61 108h104M61 129h80M61 150h70" opacity=".53" />
          </g>
          <circle cx="189" cy="174" r="32" fill="#234d68" stroke="#e9f0f4" strokeWidth="5" />
          <path d="m175 175 9 9 18-20" fill="none" stroke="white" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </section>
      <section className="landing-details" aria-labelledby="scope-heading">
        <h2 id="scope-heading">What the audit checks</h2>
        <ul>
          <li>Document title and language</li>
          <li>Heading structure and link text</li>
          <li>Image alt text and table headers</li>
        </ul>
        <p>Use a .docx file up to 10 MB. The audit focuses on six common barriers in Word documents. Review the findings and use your judgment before sharing the handout.</p>
      </section>
    </main>
  );
}
