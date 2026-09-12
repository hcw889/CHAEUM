import Link from "next/link";
import { BuildingSwitcher } from "./BuildingSwitcher";
import { StepNav } from "./StepNav";

export function BuildingPageHeader({ buildingId }: { buildingId: string }) {
  return (
    <div className="mb-2">
      <div className="mb-4 flex items-center justify-between">
        <Link href="/" className="text-lg font-semibold tracking-tight">
          채움
        </Link>
        <BuildingSwitcher currentId={buildingId} />
      </div>
      <StepNav buildingId={buildingId} />
    </div>
  );
}
