import BuildingAnalysis from "@/components/analysis/BuildingAnalysis";

export default async function DiagnosisPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <BuildingAnalysis key={id} buildingId={id} />;
}
