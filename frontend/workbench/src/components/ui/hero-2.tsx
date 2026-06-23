import React from "react";

type AuroraHeroProps = {
  children: React.ReactNode;
  className?: string;
};

type GooeyFilterProps = {
  id?: string;
  strength?: number;
};

export const GooeyFilter = ({ id = "goo-filter", strength = 10 }: GooeyFilterProps) => {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      className="gooey-filter-defs"
      width="0"
      height="0"
      viewBox="0 0 0 0"
    >
      <defs>
        <filter id={id}>
          <feGaussianBlur in="SourceGraphic" stdDeviation={strength} result="blur" />
          <feColorMatrix
            in="blur"
            type="matrix"
            values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 19 -9"
            result="goo"
          />
          <feComposite in="SourceGraphic" in2="goo" operator="atop" />
        </filter>
      </defs>
    </svg>
  );
};

export const AuroraHero = ({ children, className = "" }: AuroraHeroProps) => {
  return (
    <div className={`aurora-hero ${className}`}>
      <GooeyFilter />
      <div className="aurora-hero-glow" aria-hidden="true">
        <div className="aurora-blob aurora-blob-1" />
        <div className="aurora-blob aurora-blob-2" />
        <div className="aurora-blob aurora-blob-3" />
      </div>
      <div className="aurora-hero-content">{children}</div>
    </div>
  );
};

export default AuroraHero;
