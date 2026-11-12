import { useLayoutEffect, useState } from "react";
import { ButtonLink } from "../components/Button";
import { Icon } from "../components/Icon";

const STEPS = [
  ["Upload", "Drop in a Word document. You choose when to share it."],
  ["Audit", "Check metadata, headings, images, tables and hyperlinks for accessibility barriers."],
  ["Understand & fix", "See why each finding matters to learners, then review and approve suggested changes."],
  ["Re-audit", "Verify the improvements, then export the document or publish a link to the learner reader."],
] as const;

const CHECKS = [
  ["T", "Metadata", "Titles and language help assistive technology announce content correctly."],
  ["H", "Headings", "A logical outline for screen reader navigation."],
  ["I", "Images", "Text descriptions that explain what an image communicates."],
  ["▦", "Tables", "Header rows and structure that read in order."],
  ["↗", "Links", "Descriptive text that tells readers where a link leads."],
] as const;

const EXAMPLES = [
  ["Image has no alt text", "error", "Error"],
  ["Heading jumps from level 1 to level 3", "warning", "Warning"],
  ["Document language is set", "success", "Passed"],
] as const;

function ReaderPreview() {
  const [size, setSize] = useState(19);
  const [spacing, setSpacing] = useState(17);
  const [ruler, setRuler] = useState(false);
  const [position, setPosition] = useState(32);

  return <div className="reader-preview">
    <fieldset className="reader-preview-controls">
      <legend>Reading controls</legend>
      <label>Text size
        <input type="range" min="16" max="30" value={size}
          aria-valuetext={size + " pixels"} onChange={(event) => setSize(event.currentTarget.valueAsNumber)} />
      </label>
      <label>Line spacing
        <input type="range" min="14" max="22" value={spacing}
          aria-valuetext={String(spacing / 10)} onChange={(event) => setSpacing(event.currentTarget.valueAsNumber)} />
      </label>
      <label className="reader-preview-checkbox">
        <input type="checkbox" checked={ruler} onChange={(event) => setRuler(event.currentTarget.checked)} />
        Reading ruler
      </label>
      {ruler && <label>Ruler position
        <input type="range" min="0" max="100" value={position} onChange={(event) => setPosition(event.currentTarget.valueAsNumber)} />
      </label>}
    </fieldset>
    <article className="reader-preview-page" onPointerMove={(event) => {
      if (!ruler || event.pointerType === "touch") return;
      const bounds = event.currentTarget.getBoundingClientRect();
      setPosition(Math.round(Math.max(0, Math.min(100, (event.clientY - bounds.top) / bounds.height * 100))));
    }}>
      {ruler && <div className="reader-preview-ruler" style={{ top: position + "%" }} aria-hidden="true" />}
      <h3>Photosynthesis, simply</h3>
      <div style={{ fontSize: size / 16 + "rem", lineHeight: spacing / 10 }}>
        <p>Plants turn light into food. Inside each leaf, tiny structures called chloroplasts capture sunlight and use it to turn water and carbon dioxide into sugar.</p>
        <p>The sugar fuels growth. Plants also release oxygen, the same gas we breathe.</p>
        <p>Every learner reads differently. Try adjusting this page to see which settings make it easier to read.</p>
      </div>
    </article>
  </div>;
}

function RevealWords({ text }: { text: string }) {
  return <>{text.split(" ").map((word, index) =>
    <span key={index}><span className="landing-reveal-word">{word}</span>{" "}</span>)}</>;
}

export function Landing() {
  useLayoutEffect(() => {
    const sectionId = window.location.hash.slice(1);
    if (["engine", "checks", "reader"].includes(sectionId)) {
      // Cross-page fragment navigation can happen before React mounts the section.
      const section = document.getElementById(sectionId);
      section?.focus({ preventScroll: true });
      section?.scrollIntoView();
    }
  }, []);

  return <main id="main" className="landing" tabIndex={-1}>
    <section className="landing-hero" id="top" aria-labelledby="hero-heading">
      <div className="landing-wrap">
        <p className="landing-eyebrow">Accessibility-first EdTech</p>
        <h1 id="hero-heading">
          <span className="landing-hero-line">Learning</span>{" "}
          <span className="landing-hero-line">that fits</span>{" "}
          <span className="landing-hero-line">every reader.</span>
        </h1>
        <p className="landing-hero-description">Audit and repair educational Word documents, then share them in a reading space that students can adjust to suit them.</p>
        {import.meta.env.VITE_TEMPORARY_DEMO === "true" && <p>Temporary judges’ demo. Use the sample or a fictional document. Accounts and uploads can reset when the demo goes idle.</p>}
        <div className="product-actions">
          <ButtonLink href="/upload">Upload a document</ButtonLink>
          <ButtonLink variant="secondary" href="/account/signup?sample=1">Try a sample audit</ButtonLink>
        </div>
      </div>
    </section>
    <section className="landing-alt" id="engine" aria-labelledby="engine-heading" tabIndex={-1}>
      <div className="landing-wrap">
        <p className="landing-eyebrow">Document engine</p>
        <h2 id="engine-heading"><RevealWords text="From upload to verified, in four moves." /></h2>
        <p className="landing-lead"><RevealWords text="Educators stay in control. Each finding explains the issue and gives you a chance to review the fix." /></p>
        <ol className="landing-steps">
          {STEPS.map(([name, description], index) => <li key={name}>
            <span aria-hidden="true">0{index + 1}</span><h3>{name}</h3><p>{description}</p>
          </li>)}
        </ol>
      </div>
    </section>
    <section id="checks" aria-labelledby="checks-heading" tabIndex={-1}>
      <div className="landing-wrap">
        <p className="landing-eyebrow">What we check</p>
        <h2 id="checks-heading"><RevealWords text="Five places barriers hide." /></h2>
        <ul className="landing-checks" role="list">
          {CHECKS.map(([symbol, name, description]) => <li key={name}>
            <span className="landing-check-icon" aria-hidden="true">{symbol}</span>
            <h3>{name}</h3><p>{description}</p>
          </li>)}
        </ul>
        <ul className="landing-examples" aria-label="Example audit results">
          {EXAMPLES.map(([finding, status, label]) => <li key={finding}>
            <span>{finding}</span><span className={"landing-tag landing-tag--" + status}><Icon name={status} /> {label}</span>
          </li>)}
        </ul>
      </div>
    </section>
    <section className="landing-alt" id="reader" aria-labelledby="reader-heading" tabIndex={-1}>
      <div className="landing-wrap">
        <p className="landing-eyebrow">Learner experience</p>
        <h2 id="reader-heading"><RevealWords text="Make the page fit the student." /></h2>
        <p className="landing-lead"><RevealWords text="Try adjusting the text size, line spacing and reading ruler in this preview." /></p>
        <ReaderPreview />
      </div>
    </section>
    <section className="landing-cta" aria-labelledby="cta-heading">
      <div className="landing-wrap">
        <h2 id="cta-heading"><RevealWords text="Find barriers in your course documents." /></h2>
        <p className="landing-lead">A11yra checks six common barriers in Word documents. The audit is not a compliance guarantee.</p>
        <ButtonLink href="/account/login?next=%2Fupload">Sign in <Icon name="arrow" /></ButtonLink>
      </div>
    </section>
  </main>;
}
