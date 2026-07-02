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
        <p className="auth-kicker">FigureLearning Workbench</p>
        <h2>{"\u77e5\u8bc6\u9177"}</h2>
        <p>{"\u628a\u6536\u96c6\u3001\u5b66\u4e60\u3001\u6316\u6398\u548c\u521b\u4f5c\u653e\u5728\u4e00\u4e2a\u5b89\u9759\u53ef\u4fe1\u7684\u7f51\u9875\u5de5\u4f5c\u53f0\u91cc\u3002"}</p>
      </section>

      <section className="auth-panel" aria-labelledby="auth-title">
        <div className="auth-brand">
          <div className="brand-mark">{"\u77e5"}</div>
          <div>
            <strong>{"\u77e5\u8bc6\u9177"}</strong>
            <span>{"\u4e2a\u4eba\u77e5\u8bc6\u5e93\u4e0e\u521b\u4f5c\u5de5\u4f5c\u53f0"}</span>
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