import { cn } from "@/lib/utils";

interface SectionedProps {
  index: string;
  label: string;
  kicker?: string;
  children: React.ReactNode;
  className?: string;
  id?: string;
}

/**
 * A numbered section header. Usage:
 * <Sectioned index="03" label="REASONING SURFACE" kicker="The visible cortex">
 *   ...section content...
 * </Sectioned>
 */
export function Sectioned({
  index,
  label,
  kicker,
  children,
  className,
  id,
}: SectionedProps) {
  return (
    <section
      id={id}
      className={cn(
        "border-t border-hairline px-6 py-16 md:px-12 md:py-24",
        className,
      )}
    >
      <div className="mx-auto max-w-7xl">
        <div className="mb-12 flex items-baseline gap-6 md:mb-16">
          <span className="font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-muted">
            {index} / {label}
          </span>
          {kicker && (
            <span className="font-mono text-[0.6875rem] uppercase tracking-[0.16em] text-ash">
              {kicker}
            </span>
          )}
        </div>
        {children}
      </div>
    </section>
  );
}
