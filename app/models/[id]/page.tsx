import { ModelDetailView } from '@/components/ModelDetailView';

export default async function ModelPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ModelDetailView id={id} />;
}
