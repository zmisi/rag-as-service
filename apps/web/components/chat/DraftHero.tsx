"use client";

import { useEffect, useState } from "react";

function greetingForHour(hour: number): string {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export function DraftHero() {
  const [greeting, setGreeting] = useState("Good afternoon");

  useEffect(() => {
    setGreeting(greetingForHour(new Date().getHours()));
  }, []);

  return (
    <div className="draft-hero" data-testid="draft-hero">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        className="draft-hero-icon"
        src="/brand-cube.png"
        alt="lxzxai"
        width={56}
        height={56}
      />
      <h2 className="draft-hero-greeting">{greeting}</h2>
      <p className="draft-hero-tagline">
        I&apos;m lxzxai, your knowledge assistant.
      </p>
    </div>
  );
}
