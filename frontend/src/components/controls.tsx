/** Form controls: select, search, segmented control, slider. All keyboard accessible. */
import { useId, type ReactNode } from "react";
import { Search, X } from "lucide-react";

export function SelectField({
  label,
  value,
  onChange,
  options,
  allLabel,
  className = "",
  hideLabel = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[] | string[];
  allLabel?: string;
  className?: string;
  hideLabel?: boolean;
}) {
  const id = useId();
  const opts = options.map((o) => (typeof o === "string" ? { value: o, label: o } : o));
  return (
    <div className={`flex min-w-0 flex-col gap-0.5 ${className}`}>
      <label htmlFor={id} className={hideLabel ? "sr-only" : "section-label"}>
        {label}
      </label>
      <select id={id} className="field min-w-0 pr-6" value={value} onChange={(e) => onChange(e.target.value)}>
        {allLabel !== undefined && <option value="">{allLabel}</option>}
        {opts.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

export function SearchInput({
  value,
  onChange,
  placeholder = "Search",
  label = "Search",
  className = "",
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  label?: string;
  className?: string;
}) {
  const id = useId();
  return (
    <div className={`relative ${className}`}>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <Search size={14} className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-slate" aria-hidden />
      <input
        id={id}
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="field w-full pl-7 pr-7"
      />
      {value && (
        <button
          type="button"
          aria-label="Clear search"
          onClick={() => onChange("")}
          className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate hover:text-ink"
        >
          <X size={14} />
        </button>
      )}
    </div>
  );
}

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
  dark = false,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: ReactNode }[];
  label: string;
  dark?: boolean;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={`inline-flex rounded-[8px] border p-0.5 ${dark ? "border-ink-3 bg-ink-2" : "border-line bg-paper-2"}`}
    >
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            className={`h-7 rounded-[8px] px-2.5 text-[12.5px] font-medium transition-colors duration-150 ${
              active
                ? dark
                  ? "bg-paper text-ink"
                  : "bg-white text-ink shadow-[0_0_0_1px_var(--color-line)]"
                : dark
                  ? "text-slate hover:text-paper"
                  : "text-slate-ink hover:text-ink"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export function Slider({
  label,
  value,
  onChange,
  min,
  max,
  step,
  format,
  hint,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step: number;
  format: (v: number) => string;
  hint?: string;
}) {
  const id = useId();
  const fill = ((value - min) / (max - min)) * 100;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <label htmlFor={id} className="text-[12.5px] font-medium text-paper">
          {label}
        </label>
        <span className="num text-[15px] text-paper">{format(value)}</span>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-valuetext={format(value)}
        className="h-1.5 w-full cursor-pointer appearance-none rounded-[8px] accent-[var(--color-brass)]"
        style={{ background: `linear-gradient(to right, var(--color-brass) ${fill}%, var(--color-ink-3) ${fill}%)` }}
      />
      <div className="flex justify-between font-mono text-[10px] text-slate">
        <span>{format(min)}</span>
        {hint && <span className="text-center">{hint}</span>}
        <span>{format(max)}</span>
      </div>
    </div>
  );
}
