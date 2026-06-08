import { LeadScore } from "@/types/interview";

const leadMeta = {
  HOT: {
    icon: "🟢",
    className: "border-green-200 bg-gradient-to-br from-green-50 to-white text-green-800",
  },
  WARM: {
    icon: "🟡",
    className: "border-amber-200 bg-gradient-to-br from-amber-50 to-white text-amber-800",
  },
  INFO: {
    icon: "🔵",
    className: "border-sky-200 bg-gradient-to-br from-sky-50 to-white text-sky-800",
  },
};

type LeadBadgeProps = {
  lead: LeadScore;
};

export function LeadBadge({ lead }: LeadBadgeProps) {
  const meta = leadMeta[lead.label];

  return (
    <div className={`rounded-lg border p-5 shadow-sm ${meta.className}`}>
      <div className="flex items-center gap-2 text-lg font-semibold">
        <span className="rounded-full bg-white/80 p-1 shadow-sm" aria-hidden>
          {meta.icon}
        </span>
        <span>{lead.title}</span>
      </div>
      <p className="mt-2 text-sm leading-6">{lead.reason}</p>
    </div>
  );
}
