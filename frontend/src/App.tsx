import { useState } from 'react'
import './App.css'
import { useAuth } from './contexts/AuthContext'
import Header from './components/Header'
import AuthModal from './components/AuthModal'
import LandingPage from './components/LandingPage'
import Dashboard from './components/Dashboard'

function App() {
  const { user, isAuthenticated, isLoading } = useAuth();
  const [showAuthModal, setShowAuthModal] = useState(false);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }
  return (
    <>
      <Header />


      {isAuthenticated ? (
        <Dashboard />
      ) : <LandingPage />}

      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        initialMode="login"
      />
    </>
  );
}

export default App
