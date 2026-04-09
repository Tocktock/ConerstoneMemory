import { ConfigWorkspace } from "@/components/workspace-sections";
import type { ConfigKind } from "@/lib/api/types";

const allowedKinds: ConfigKind[] = ["api-ontology", "memory-ontology", "policy-profile"];

export default async function ConfigPage({ params }: { params: Promise<{ kind: string }> }) {
  const { kind } = await params;
  const normalizedKind = kind as ConfigKind;

  if (!allowedKinds.includes(normalizedKind)) {
    return (
      <div className="panel p-6 text-sm text-slate-300">
        Unknown config document kind: <span className="font-mono text-white">{kind}</span>
      </div>
    );
  }

  return <ConfigWorkspace kind={normalizedKind} />;
}
