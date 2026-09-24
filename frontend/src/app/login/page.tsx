"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useRouter } from "next/navigation";
import { z } from "zod";

import { friendlyApiMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";

const schema = z.object({
  email: z.string().trim().email("Enter a valid email address."),
  password: z
    .string()
    .min(1, "Enter your password.")
    .max(128, "Password is too long."),
});

type LoginValues = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const { status, login } = useAuth();
  const [submitError, setSubmitError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  useEffect(() => {
    if (status === "authenticated") {
      router.replace("/dashboard");
    }
  }, [router, status]);

  async function onSubmit(values: LoginValues) {
    setSubmitError(null);
    try {
      await login(values);
      router.replace("/dashboard");
    } catch (error) {
      setSubmitError(friendlyApiMessage(error));
    }
  }

  return (
    <main className="login-page">
      <section className="login-context" aria-label="Application information">
        <div className="login-seal" aria-hidden="true">
          LM
        </div>
        <p className="login-kicker">Government laboratory workflow</p>
        <h1>NAWI Type Evaluation & Test Reporting</h1>
        <p>
          Structured evaluation, review and standardized reporting for
          Non-Automatic Weighing Instruments under the OIML R76 workflow.
        </p>

        <div className="login-principles">
          <div>
            <strong>Deterministic evaluation</strong>
            <span>
              Regulatory decisions are calculated by the backend engine.
            </span>
          </div>
          <div>
            <strong>Controlled workflow</strong>
            <span>
              Testing, review, approval and report issue remain distinct.
            </span>
          </div>
          <div>
            <strong>Traceable records</strong>
            <span>
              Versions, retests, revisions and report history are preserved.
            </span>
          </div>
        </div>
      </section>

      <section className="login-panel">
        <div className="login-card">
          <p className="page-eyebrow">Authorized access</p>
          <h2>Sign in</h2>
          <p className="login-helper">
            Use the account issued for your laboratory or administrative role.
          </p>

          <form onSubmit={handleSubmit(onSubmit)} noValidate>
            <label className="form-field">
              <span>Email address</span>
              <input
                type="email"
                autoComplete="username"
                aria-invalid={Boolean(errors.email)}
                {...register("email")}
              />
              {errors.email ? (
                <small className="field-error">{errors.email.message}</small>
              ) : null}
            </label>

            <label className="form-field">
              <span>Password</span>
              <input
                type="password"
                autoComplete="current-password"
                aria-invalid={Boolean(errors.password)}
                {...register("password")}
              />
              {errors.password ? (
                <small className="field-error">{errors.password.message}</small>
              ) : null}
            </label>

            {submitError ? (
              <div className="form-alert" role="alert">
                {submitError}
              </div>
            ) : null}

            <button
              className="button button-primary login-submit"
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <p className="authorized-note">
            Authorized laboratory personnel only. Activity is subject to the
            backend audit and permission controls.
          </p>
        </div>
      </section>
    </main>
  );
}
