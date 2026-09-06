import { FileText } from "lucide-react";
import Link from "next/link";
import { TenderSchematic } from "./sign-in-tender-schematic";

const MONO_LABEL =
  "text-muted-foreground font-mono text-[10px] tracking-[0.14em] uppercase";

function CornerMark({ className }: { className?: string }) {
  return (
    <span aria-hidden className={`absolute size-2.5 ${className}`}>
      <span className="bg-border absolute top-1/2 left-0 h-px w-full -translate-y-1/2" />
      <span className="bg-border absolute top-0 left-1/2 h-full w-px -translate-x-1/2" />
    </span>
  );
}

export function SignInBrandPanel() {
  return (
    <div className="bg-muted/30 relative hidden overflow-hidden border-r border-dashed lg:block">
      <CornerMark className="top-6 left-6" />
      <CornerMark className="right-6 bottom-6" />

      <div className="relative z-10 flex h-full flex-col justify-between p-12">
        <Link href="/" className="group flex w-fit items-center gap-2.5">
          <span className="bg-primary text-primary-foreground flex size-9 items-center justify-center rounded-md transition-transform group-hover:scale-105">
            <FileText className="size-4.5" />
          </span>
          <span className="flex flex-col leading-tight">
            <span className="text-[15px] font-semibold tracking-tight">
              Extracto AI
            </span>
            <span className="text-muted-foreground text-xs tracking-tight">
              RFP Automation
            </span>
          </span>
        </Link>

        <div className="flex justify-center py-4">
          <TenderSchematic />
        </div>

        <div>
          <div className="flex items-center gap-4">
            <span className="text-primary text-[11px] font-semibold tracking-[0.18em] uppercase">
              Secure access
            </span>
            <span aria-hidden className="bg-border h-px flex-1" />
          </div>

          <h2 className="mt-5 max-w-md text-3xl font-semibold tracking-tight text-balance">
            Streamline your RFP and specification workflows
          </h2>
          <p className="text-muted-foreground mt-3 max-w-md text-sm leading-relaxed text-pretty">
            Upload RFP documents, extract requirements with AI, and generate
            compliant responses — all in one place.
          </p>

          <div className="mt-8 flex items-center justify-between gap-4">
            <span className={MONO_LABEL}>AI-powered extraction</span>
            <span aria-hidden className="bg-border h-px flex-1" />
            <span className={MONO_LABEL}>Private &amp; secure</span>
          </div>
        </div>
      </div>
    </div>
  );
}
