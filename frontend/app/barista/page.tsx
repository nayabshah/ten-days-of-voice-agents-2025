import { headers } from 'next/headers';
import BaristaPage from '@/components/barista-page';
import { getBaristaConfig } from '@/lib/utils';

export default async function Page() {
  const hdrs = await headers();
  const baristaConfig = await getBaristaConfig(hdrs);

  return <BaristaPage baristaConfig={baristaConfig} />;
}
