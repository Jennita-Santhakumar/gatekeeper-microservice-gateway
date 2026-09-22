import { useState } from "react";

import { GatewayDashboard } from "./components/GatewayDashboard";
import { LoginForm } from "./components/LoginForm";
import { getToken } from "./lib/api";

export default function App() {
  const [authed, setAuthed] = useState(() => getToken() !== null);

  if (!authed) {
    return <LoginForm onSuccess={() => setAuthed(true)} />;
  }

  return <GatewayDashboard onLogout={() => setAuthed(false)} />;
}
