import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { Lock, LogIn, RefreshCw, Ticket } from "lucide-react";
import { authApi } from "../api";
import type { AuthContext } from "../api";
import { onAuthExpired } from "../apiCore";

type AuthGateProps = {
  children:
    | ReactNode
    | ((props: { context: AuthContext; onContextChange: (nextContext: AuthContext) => void }) => ReactNode);
};

type Mode = "login" | "register";

const signedOutCloudContext: AuthContext = {
  deploymentMode: "cloud",
  authenticated: false,
  user: null,
  workspace: null,
};

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
  const title = useMemo(() => (mode === "login" ? "\u767b\u5f55\u77e5\u8bc6\u9177" : "\u4f7f\u7528\u9080\u8bf7\u7801\u52a0\u5165"), [mode]);

  useEffect(() => {
    let active = true;
    authApi
      .me()
      .then((payload) => {
        if (active) setContext(payload);
      })
      .catch((requestError) => {
        if (!active) return;
        setContext(signedOutCloudContext);
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

  useEffect(() => onAuthExpired(() => {
    setContext((current) => ({
      deploymentMode: current?.deploymentMode ?? "cloud",
      authenticated: false,
      user: null,
      workspace: null,
    }));
    setError("\u767b\u5f55\u5df2\u5931\u6548\uff0c\u8bf7\u91cd\u65b0\u767b\u5f55\u3002");
  }), []);

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
      setPassword("");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "\u8ba4\u8bc1\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <main className="auth-screen auth-screen--loading">
        <div className="auth-panel auth-panel--loading">
          <RefreshCw size={20} aria-hidden="true" />
          <span>{"\u6b63\u5728\u8fdb\u5165\u77e5\u8bc6\u9177..."}</span>
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
    <main className="auth-screen auth-screen--paper">
      <section className="auth-intro" aria-label="\u77e5\u8bc6\u9177\u4ecb\u7ecd">
        <p className="auth-kicker">AI LONGFORM WORKBENCH</p>
        <h2>{"\u628a\u7d20\u6750\u53d8\u6210\u53ef\u53d1\u5e03\u7684\u6df1\u5ea6\u6587\u7ae0"}</h2>
        <p className="auth-tagline">{"\u4ece\u7d20\u6750\u6574\u7406\u5230\u6df1\u5ea6\u6587\u7ae0\uff0c\u4e00\u6761\u94fe\u8def\u5b8c\u6210"}</p>
      </section>

      <section className="auth-panel" aria-labelledby="auth-title">
        <div className="auth-brand">
          <div className="brand-mark">{"\u77e5"}</div>
          <div>
            <strong>{"\u77e5\u8bc6\u9177"}</strong>
            <span>{"\u4e2d\u6587\u77e5\u8bc6\u521b\u4f5c\u8005\u7684 AI \u957f\u6587\u5de5\u4f5c\u53f0"}</span>
          </div>
        </div>
        <div className="auth-heading">
          <Lock size={22} aria-hidden="true" />
          <h1 id="auth-title">{title}</h1>
        </div>
        <form className="auth-form" onSubmit={submit}>
          {mode === "login" ? (
            <label>
              <span>{"\u90ae\u7bb1\u6216\u7528\u6237\u540d"}</span>
              <input value={identifier} onChange={(event) => setIdentifier(event.target.value)} autoComplete="username" required />
            </label>
          ) : (
            <>
              <label>
                <span>{"\u9080\u8bf7\u7801"}</span>
                <input value={inviteCode} onChange={(event) => setInviteCode(event.target.value)} autoComplete="one-time-code" required />
              </label>
              <label>
                <span>{"\u90ae\u7bb1"}</span>
                <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required />
              </label>
              <label>
                <span>{"\u7528\u6237\u540d"}</span>
                <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required />
              </label>
            </>
          )}
          <label>
            <span>{"\u5bc6\u7801"}</span>
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
            <span>{isSubmitting ? "\u63d0\u4ea4\u4e2d..." : mode === "login" ? "\u767b\u5f55" : "\u52a0\u5165\u5185\u6d4b"}</span>
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
          {mode === "login" ? "\u4f7f\u7528\u9080\u8bf7\u7801\u6ce8\u518c" : "\u5df2\u6709\u8d26\u53f7\uff0c\u8fd4\u56de\u767b\u5f55"}
        </button>
        <nav className="auth-policy-links" aria-label="\u5185\u6d4b\u8bf4\u660e">
          <a href="/public-beta" target="_blank" rel="noreferrer">{"\u5185\u6d4b\u8bf4\u660e"}</a>
          <a href="/privacy" target="_blank" rel="noreferrer">{"\u9690\u79c1\u8bf4\u660e"}</a>
          <a href="/data-retention" target="_blank" rel="noreferrer">{"\u6570\u636e\u4fdd\u5b58"}</a>
        </nav>
      </section>
    </main>
  );
}
