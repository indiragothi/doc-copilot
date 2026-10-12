import { BrowserRouter, Route, Routes } from "react-router-dom"

import { AuthProvider } from "@/components/auth-provider"
import { ProtectedRoute } from "@/components/protected-route"
import HomePage from "@/pages/home"
import SignInPage from "@/pages/sign-in"
import SignUpPage from "@/pages/sign-up"

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<SignInPage />} />
          <Route path="/signup" element={<SignUpPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<HomePage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
