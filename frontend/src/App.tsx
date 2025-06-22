import { useState } from 'react'
import './App.css'
import { useAuth } from './contexts/AuthContext'
import Header from './components/Header'
import AuthModal from './components/AuthModal'

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
    <div className="min-h-screen bg-gray-100">
      <Header />
      
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
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
          ) : (
            <div className="flex items-center justify-center">
              <div className="max-w-md mx-auto bg-white rounded-xl shadow-md overflow-hidden">
                <div className="p-8">
                  <div className="uppercase tracking-wide text-sm text-indigo-500 font-semibold">
                    Baruch Study Rooms
                  </div>
                  <h1 className="block mt-1 text-lg leading-tight font-medium text-black">
                    Welcome to the Study Room Booking System
                  </h1>
                  <p className="mt-2 text-gray-500">
                    Sign in with your Baruch email to find and book study rooms for your academic needs.
                  </p>
                  <button 
                    onClick={() => setShowAuthModal(true)}
                    className="mt-4 bg-indigo-500 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded"
                  >
                    Get Started
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        initialMode="login"
      />
    </div>
  );
}

export default App
