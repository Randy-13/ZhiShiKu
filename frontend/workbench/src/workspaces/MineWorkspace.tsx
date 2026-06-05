import { useState } from "react";
import type { ReactNode } from "react";
import type { KnowledgeItem, MiningResult } from "../domain";
import type { Translator } from "../i18n";
import { EmptyState } from "../components/EmptyState";
import { PrimaryTaskPanel } from "../components/PrimaryTaskPanel";

const zhRoles = ["投资人", "写作者", "研究员", "散户", "创业者"];
const enRoles = ["Investor", "Writer", "Researcher", "Retail reader", "Founder"];

export function MineWorkspace({
  t,
  language,
  knowledge,
  selectedKnowledge,
  result,
  rightRail,
  onSelectKnowledge,
  onRunMining,
}: {
  t: Translator;
  language: "zh" | "en";
  knowledge: KnowledgeItem[];
  selectedKnowledge?: KnowledgeItem;
  result?: MiningResult;
  rightRail: ReactNode;
  onSelectKnowledge: (id: string) => void;
  onRunMining: (role: string, question: string) => void;
}) {
  const roles = language === "zh" ? zhRoles : enRoles;
  const [role, setRole] = useState(roles[0]);
  const [question, setQuestion] = useState(
    language === "zh"
      ? "这条知识对投资判断或内容创作有什么反直觉价值？"
      : "What counterintuitive value does this knowledge have for judgment or creation?",
  );

  return (
    <section className="workspace-layout">
      <div className="workspace-main">
        <PrimaryTaskPanel
          eyebrow={t("common.primary")}
          title={t("mine.roles")}
          body={t("mine.body")}
          action={t("mine.primary")}
          disabled={!selectedKnowledge}
          disabledReason={t("mine.needSelect")}
          onAction={() => onRunMining(role, question)}
        >
          <div className="input-row" role="group" aria-label={t("mine.roles")}>
            {roles.map((item) => (
              <button className={role === item ? "choice active" : "choice"} type="button" key={item} onClick={() => setRole(item)}>
                {item}
              </button>
            ))}
          </div>
          <label className="full-field">
            <span>{t("mine.question")}</span>
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
          </label>
        </PrimaryTaskPanel>

        <section className="content-panel">
          <h2>{t("mine.knowledge")}</h2>
          {knowledge.length === 0 ? (
            <EmptyState title={t("mine.empty")} body={t("mine.empty.body")} />
          ) : (
            <div className="queue-list">
              {knowledge.map((item) => (
                <button
                  className={selectedKnowledge?.id === item.id ? "queue-row selected" : "queue-row"}
                  type="button"
                  key={item.id}
                  onClick={() => onSelectKnowledge(item.id)}
                >
                  <strong>{item.title}</strong>
                  <span>{item.status}</span>
                </button>
              ))}
            </div>
          )}
        </section>

        {result ? (
          <section className="content-panel">
            <h2>{t("mine.result")}</h2>
            <div className="context-stack">
              <h3>{result.role}</h3>
              <p>
                <strong>{language === "zh" ? "主张：" : "Claim: "}</strong>
                {result.claim}
              </p>
              <p>
                <strong>{language === "zh" ? "证据：" : "Evidence: "}</strong>
                {result.evidence}
              </p>
              <p>
                <strong>{language === "zh" ? "反方：" : "Counterpoint: "}</strong>
                {result.counterpoint}
              </p>
            </div>
          </section>
        ) : null}
      </div>

      {rightRail}
    </section>
  );
}
