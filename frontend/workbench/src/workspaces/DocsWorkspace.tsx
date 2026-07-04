import { ArrowRight, Search } from "lucide-react";
import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { Language } from "../domain";
import type { Translator } from "../i18n";
import zhHelp from "../docs/help.zh.md?raw";
import enHelp from "../docs/help.en.md?raw";

type DocSection = {
  id: string;
  title: string;
  content: string;
};

type DocHeading = {
  id: string;
  depth: number;
  title: string;
};

const docsByLanguage: Record<Language, string> = {
  zh: zhHelp,
  en: enHelp,
};

export function DocsWorkspace({
  t,
  language,
}: {
  t: Translator;
  language: Language;
}) {
  const [query, setQuery] = useState("");
  const parsed = useMemo(() => parseDocument(docsByLanguage[language]), [language]);
  const [selectedId, setSelectedId] = useState<string>();
  const normalizedQuery = query.trim().toLowerCase();
  const filteredSections = useMemo(() => {
    if (!normalizedQuery) return parsed.sections;
    return parsed.sections.filter((section) =>
      `${section.title}\n${section.content}`.toLowerCase().includes(normalizedQuery),
    );
  }, [normalizedQuery, parsed.sections]);
  const selectedSection =
    (normalizedQuery
      ? filteredSections.find((section) => section.id === selectedId)
      : parsed.sections.find((section) => section.id === selectedId)) ??
    filteredSections[0] ??
    parsed.sections[0];
  const headings = useMemo(
    () => (selectedSection ? extractHeadings(selectedSection.content) : []),
    [selectedSection],
  );

  return (
    <section className="docs-workspace">
      <aside className="docs-sidebar" aria-label={t("docs.nav")}>
        <div className="docs-search">
          <Search size={16} />
          <input
            type="search"
            value={query}
            placeholder={t("docs.search.placeholder")}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <nav className="docs-section-list">
          {filteredSections.length ? (
            filteredSections.map((section) => (
              <button
                className={section.id === selectedSection?.id ? "docs-section-link active" : "docs-section-link"}
                type="button"
                key={section.id}
                onClick={() => setSelectedId(section.id)}
              >
                <span>{section.title}</span>
                <ArrowRight size={15} />
              </button>
            ))
          ) : (
            <div className="empty-state">
              <strong>{t("docs.search.empty")}</strong>
              <p>{t("docs.search.empty.body")}</p>
            </div>
          )}
        </nav>
      </aside>
      <article className="docs-reader" aria-labelledby="docs-title">
        <div className="docs-reader-header">
          <span>{t("docs.reader.eyebrow")}</span>
          <h1 id="docs-title">{selectedSection?.title ?? parsed.title}</h1>
          <p>{t("docs.reader.body")}</p>
        </div>
        {selectedSection ? (
          <div className="docs-markdown">{renderMarkdown(selectedSection.content)}</div>
        ) : null}
      </article>
      <aside className="docs-toc" aria-label={t("docs.toc")}>
        <strong>{t("docs.toc")}</strong>
        {headings.length ? (
          <nav>
            {headings.map((heading) => (
              <a
                className={heading.depth > 3 ? "docs-toc-link nested" : "docs-toc-link"}
                href={`#${heading.id}`}
                key={heading.id}
              >
                {heading.title}
              </a>
            ))}
          </nav>
        ) : (
          <p>{t("docs.toc.empty")}</p>
        )}
      </aside>
    </section>
  );
}

function parseDocument(markdown: string): { title: string; sections: DocSection[] } {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const title = lines.find((line) => line.startsWith("# "))?.replace(/^#\s+/, "").trim() || "Docs";
  const sections: DocSection[] = [];
  let current: { title: string; lines: string[] } | undefined;

  for (const line of lines) {
    if (line.startsWith("# ")) continue;
    if (line.startsWith("## ")) {
      if (current) sections.push(toSection(current, sections.length));
      current = { title: line.replace(/^##\s+/, "").trim(), lines: [] };
      continue;
    }
    if (current) current.lines.push(line);
  }
  if (current) sections.push(toSection(current, sections.length));
  return { title, sections };
}

function toSection(section: { title: string; lines: string[] }, index: number): DocSection {
  return {
    id: slugify(section.title, index),
    title: section.title,
    content: section.lines.join("\n").trim(),
  };
}

function extractHeadings(markdown: string): DocHeading[] {
  return markdown
    .split("\n")
    .map((line, index) => {
      const match = /^(#{3,4})\s+(.+)$/.exec(line);
      if (!match) return undefined;
      return {
        id: slugify(match[2], index),
        depth: match[1].length,
        title: match[2].trim(),
      };
    })
    .filter((heading): heading is DocHeading => Boolean(heading));
}

function renderMarkdown(markdown: string): ReactNode[] {
  const lines = markdown.split("\n");
  const nodes: ReactNode[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }

    if (line.startsWith("```")) {
      const code: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith("```")) {
        code.push(lines[index]);
        index += 1;
      }
      index += 1;
      nodes.push(
        <pre key={`code-${index}`}>
          <code>{code.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    const headingMatch = /^(#{3,4})\s+(.+)$/.exec(line);
    if (headingMatch) {
      const title = headingMatch[2].trim();
      const id = slugify(title, index);
      nodes.push(
        headingMatch[1].length === 3 ? (
          <h2 id={id} key={id}>{parseInline(title)}</h2>
        ) : (
          <h3 id={id} key={id}>{parseInline(title)}</h3>
        ),
      );
      index += 1;
      continue;
    }

    if (line.startsWith("- ")) {
      const items: string[] = [];
      while (index < lines.length && lines[index].startsWith("- ")) {
        items.push(lines[index].replace(/^-\s+/, ""));
        index += 1;
      }
      nodes.push(
        <ul key={`list-${index}`}>
          {items.map((item, itemIndex) => (
            <li key={`${item}-${itemIndex}`}>{parseInline(item)}</li>
          ))}
        </ul>,
      );
      continue;
    }

    const paragraph: string[] = [];
    while (
      index < lines.length &&
      lines[index].trim() &&
      !lines[index].startsWith("```") &&
      !lines[index].startsWith("### ") &&
      !lines[index].startsWith("#### ") &&
      !lines[index].startsWith("- ")
    ) {
      paragraph.push(lines[index]);
      index += 1;
    }
    nodes.push(<p key={`paragraph-${index}`}>{parseInline(paragraph.join(" "))}</p>);
  }

  return nodes;
}

function parseInline(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /(\[[^\]]+\]\([^)]+\)|`[^`]+`|\*\*[^*]+\*\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) nodes.push(text.slice(lastIndex, match.index));
    const token = match[0];
    if (token.startsWith("[")) {
      const linkMatch = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(token);
      if (linkMatch) {
        nodes.push(renderLink(linkMatch[1], linkMatch[2], nodes.length));
      }
    } else if (token.startsWith("`")) {
      nodes.push(<code key={`code-${nodes.length}`}>{token.slice(1, -1)}</code>);
    } else if (token.startsWith("**")) {
      nodes.push(<strong key={`strong-${nodes.length}`}>{token.slice(2, -2)}</strong>);
    }
    lastIndex = pattern.lastIndex;
  }
  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return nodes;
}

function renderLink(label: string, href: string, key: number) {
  const isExternal = /^https?:\/\//.test(href);
  return (
    <a
      href={href}
      key={`link-${key}`}
      target={isExternal ? "_blank" : undefined}
      rel={isExternal ? "noreferrer" : undefined}
    >
      {label}
    </a>
  );
}

function slugify(value: string, fallback: number) {
  const slug = value
    .trim()
    .toLowerCase()
    .replace(/[^\p{Letter}\p{Number}]+/gu, "-")
    .replace(/^-+|-+$/g, "");
  return slug || `section-${fallback}`;
}
