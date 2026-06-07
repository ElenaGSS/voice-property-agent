import { LeadScore } from "@/types/interview";

const leadMeta = {
  HOT: {
    icon: "🟢",
    className: "border-green-200 bg-green-50 text-green-800",
  },
  WARM: {
    icon: "🟡",
    className: "border-yellow-200 bg-yellow-50 text-yellow-800",
  },
  INFO: {
    icon: "🔵",
    className: "border-blue-200 bg-blue-50 text-blue-800",
  },
};

type LeadBadgeProps = {
  lead: LeadScore;
};

export function LeadBadge({ lead }: LeadBadgeProps) {
  const meta = leadMeta[lead.label];

  return (
    <div className={`rounded-lg border p-4 ${meta.className}`}>
      <div className="flex items-center gap-2 text-lg font-semibold">
        <span aria-hidden>{meta.icon}</span>
        <span>{lead.title}</span>
      </div>
      <p className="mt-2 text-sm leading-6">{lead.reason}</p>
    </div>
  );
}
