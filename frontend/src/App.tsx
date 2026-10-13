import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/AppLayout";
import { AddIngredientsPage } from "./pages/AddIngredientsPage";
import { KitchenPage } from "./pages/KitchenPage";
import { MorePage } from "./pages/MorePage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { ReviewDraftPage } from "./pages/ReviewDraftPage";

export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to="/cook" replace />} />
        <Route path="/cook" element={<PlaceholderPage title="Cook" />} />
        <Route path="/buy" element={<PlaceholderPage title="Buy" />} />
        <Route path="/more" element={<MorePage />} />
        <Route path="/more/kitchen" element={<KitchenPage />} />
        <Route path="/more/add" element={<AddIngredientsPage />} />
        <Route path="/more/preferences" element={<PlaceholderPage title="Preferences" />} />
        <Route path="/more/history" element={<PlaceholderPage title="Kitchen history & undo" />} />
      </Route>
      <Route element={<AppLayout tabBar={false} />}>
        <Route path="/more/add/review" element={<ReviewDraftPage />} />
      </Route>
      <Route path="/onboarding" element={<PlaceholderPage title="Welcome" />} />
    </Routes>
  );
}
