"use client";

import { useEffect, useState } from "react";

type ThemeMode = "dark" | "light";

function applyTheme(theme: ThemeMode) {
  document.documentElement.classList.toggle("dark", theme === "dark");
  localStorage.setItem("maa-theme", theme);
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<ThemeMode>(() => {
    if (typeof window === "undefined") {
      return "dark";
    }

    const savedTheme = localStorage.getItem("maa-theme");

    if (savedTheme === "dark" || savedTheme === "light") {
      return savedTheme;
    }

    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    return prefersDark ? "dark" : "light";
  });

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  function handleToggle() {
    const nextTheme: ThemeMode = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
  }

  return (
    <button
      type="button"
      onClick={handleToggle}
      className="material-chip inline-flex h-11 items-center justify-center rounded-2xl px-4 text-sm font-medium text-slate-200 transition hover:border-slate-600 hover:text-white"
      aria-label="Toggle theme"
    >
      Theme
    </button>
  );
}
