import DriveCrawlRunsList from "@/components/drive/DriveCrawlRunsList";

export const metadata = {
  title: "Crawl runs · Google Drive",
  description: "History of Google Drive crawl jobs",
};

export default function DriveCrawlRunsPage() {
  return <DriveCrawlRunsList />;
}
