import { useState } from 'react'
import './App.css'
import { useAuth } from './contexts/AuthContext'
import Header from './components/Header'
import AuthModal from './components/AuthModal'
import LandingPage from './components/LandingPage'

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
        <div className="bg-white rounded-lg shadow-sm p-8">
          <div className="text-center">
            <h1 className="text-3xl font-bold text-gray-900 mb-4">
              Welcome back, {user?.firstName}!
            </h1>
            <p className="text-gray-600 mb-8">
              Ready to book a study room for your academic needs?
            </p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8">
              <div className="bg-indigo-50 p-6 rounded-lg">
                <h3 className="text-lg font-semibold text-indigo-900 mb-2">Quick Book</h3>
                <p className="text-indigo-700 text-sm mb-4">Find available rooms right now</p>
                <button className="bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700">
                  Book Now
                </button>
              </div>

              <div className="bg-green-50 p-6 rounded-lg">
                <h3 className="text-lg font-semibold text-green-900 mb-2">My Bookings</h3>
                <p className="text-green-700 text-sm mb-4">View and manage your reservations</p>
                <button className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700">
                  View Bookings
                </button>
              </div>

              <div className="bg-purple-50 p-6 rounded-lg">
                <h3 className="text-lg font-semibold text-purple-900 mb-2">Room Monitor</h3>
                <p className="text-purple-700 text-sm mb-4">Get notified when rooms become available</p>
                <button className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700">
                  Set Monitor
                </button>
              </div>
            </div>
          </div>
        </div>
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
