import { useState } from "react";
import type { ReactNode } from "react";
import type { MiningResult } from "../domain";
import type { Translator } from "../i18n";
import { PrimaryTaskPanel } from "../components/PrimaryTaskPanel";

const zhRoles = ["投资人", "写作者", "研究员", "散户", "创业者"];
const enRoles = ["Investor", "Writer", "Researcher", "Retail reader", "Founder"];

export function MineWorkspace({
  t,
  language,
  result,
  rightRail,
  onRunMining,
}: {
  t: Translator;
  language: "zh" | "en";
  result?: MiningResult;
  rightRail: ReactNode;
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
          disabled
          disabledReason={language === "zh" ? "挖掘对象导入将后续单独接入。" : "Mining object import will be connected later."}
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
