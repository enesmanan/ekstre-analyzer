import { createBrowserRouter } from "react-router";
import { Layout } from "./pages/Layout";
import { OverviewPage } from "./pages/Overview";
import { SettingsPage } from "./pages/Settings";
import { TransactionsPage } from "./pages/Transactions";
import { UploadPage } from "./pages/Upload";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <UploadPage /> },
      { path: "overview", element: <OverviewPage /> },
      { path: "transactions", element: <TransactionsPage /> },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
]);
