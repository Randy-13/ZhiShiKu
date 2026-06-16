import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { Lock, LogIn, RefreshCw, Ticket } from "lucide-react";
import { authApi } from "../api";
import type { AuthContext } from "../api";
import { AuroraHero } from "./ui/hero-2";

type AuthGateProps = {
  children:
    | ReactNode
    | ((props: { context: AuthContext; onContextChange: (nextContext: AuthContext) => void }) => ReactNode);
};

type Mode = "login" | "register";

export function AuthGate({ children }: AuthGateProps) {
  const [context, setContext] = useState<AuthContext>();
  const [mode, setMode] = useState<Mode>("login");
  const [identifier, setIdentifier] = useState("");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isCloud = context?.deploymentMode === "cloud" || !context;
  const canEnter = context?.authenticated && context.user;
  const title = useMemo(() => (mode === "login" ? "登录知识酷" : "使用邀请码加入"), [mode]);

  useEffect(() => {
    let active = true;
    authApi
      .me()
      .then((payload) => {
        if (active) setContext(payload);
      })
      .catch((requestError) => {
        if (!active) return;
        setContext({
          deploymentMode: "cloud",
          authenticated: false,
          user: null,
          workspace: null,
        });
        if (requestError instanceof Error && !requestError.message.includes("401")) {
          setError(requestError.message);
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      const payload =
        mode === "login"
          ? await authApi.login(identifier, password)
          : await authApi.registerWithInvite({ inviteCode, email, username, password });
      setContext(payload);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "认证失败，请稍后重试");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <main className="auth-screen auth-screen--loading">
        <div className="auth-panel auth-panel--loading">
          <RefreshCw size={20} aria-hidden="true" />
          <span>正在进入知识酷...</span>
        </div>
      </main>
    );
  }

  if ((!isCloud || canEnter) && context) {
    return (
      <>
        {typeof children === "function"
          ? children({ context, onContextChange: setContext })
          : children}
      </>
    );
  }

  return (
    <main className="auth-screen">
      <AuroraHero className="auth-aurora">
        <section className="auth-intro" aria-label="知识酷介绍">
          <p className="auth-kicker">FigureLearning Workbench</p>
          <h2>知识酷</h2>
          <p>把素材收集、知识沉淀、视角挖掘和公众号创作放进一个安静的本地工作台。</p>
        </section>
      </AuroraHero>

      <section className="auth-panel" aria-labelledby="auth-title">
        <div className="auth-brand">
          <div className="brand-mark">知</div>
          <div>
            <strong>知识酷</strong>
            <span>个人知识库与创作工作台</span>
          </div>
        </div>
        <div className="auth-heading">
          <Lock size={22} aria-hidden="true" />
          <h1 id="auth-title">{title}</h1>
        </div>
        <form className="auth-form" onSubmit={submit}>
          {mode === "login" ? (
            <label>
              <span>邮箱或用户名</span>
              <input value={identifier} onChange={(event) => setIdentifier(event.target.value)} autoComplete="username" required />
            </label>
          ) : (
            <>
              <label>
                <span>邀请码</span>
                <input value={inviteCode} onChange={(event) => setInviteCode(event.target.value)} autoComplete="one-time-code" required />
              </label>
              <label>
                <span>邮箱</span>
                <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required />
              </label>
              <label>
                <span>用户名</span>
                <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required />
              </label>
            </>
          )}
          <label>
            <span>密码</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              minLength={mode === "register" ? 8 : undefined}
              required
            />
          </label>
          {error ? <p className="auth-error">{error}</p> : null}
          <button className="primary-action auth-submit" type="submit" disabled={isSubmitting}>
            {mode === "login" ? <LogIn size={18} aria-hidden="true" /> : <Ticket size={18} aria-hidden="true" />}
            <span>{isSubmitting ? "提交中..." : mode === "login" ? "登录" : "加入内测"}</span>
          </button>
        </form>
        <button
          className="ghost-button auth-switch"
          type="button"
          onClick={() => {
            setError("");
            setPassword("");
            setMode((current) => (current === "login" ? "register" : "login"));
          }}
        >
          {mode === "login" ? "使用邀请码注册" : "已有账号，返回登录"}
        </button>
        <nav className="auth-policy-links" aria-label="内测说明">
          <a href="/public-beta" target="_blank" rel="noreferrer">
            内测说明
          </a>
          <a href="/privacy" target="_blank" rel="noreferrer">
            隐私说明
          </a>
          <a href="/data-retention" target="_blank" rel="noreferrer">
            数据保存
          </a>
        </nav>
      </section>
    </main>
  );
}
