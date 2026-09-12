import Link from "next/link";
import { BuildingSwitcher } from "./BuildingSwitcher";
import { Wordmark } from "./Logo";
import { StepNav } from "./StepNav";

export function BuildingPageHeader({ buildingId }: { buildingId: string }) {
  return (
    <div className="mb-2">
      <div className="mb-4 flex items-center justify-between">
        <Link href="/" className="text-lg">
          <Wordmark />
        </Link>
        <BuildingSwitcher currentId={buildingId} />
      </div>
      <StepNav buildingId={buildingId} />
    </div>
  );
}
