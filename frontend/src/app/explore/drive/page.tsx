import DriveExplorer from "@/components/drive/DriveExplorer";

export const metadata = {
  title: "Files · Google Drive",
  description: "Browse indexed public Google Drive files",
};

export default function DrivePage() {
  return <DriveExplorer />;
}
