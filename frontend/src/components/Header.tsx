import { useState, useRef, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import AuthModal from './AuthModal';
import UserProfile from './UserProfile';

const Header = () => {
  const { user, isAuthenticated, isLoading } = useAuth();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showUserProfile, setShowUserProfile] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setShowUserProfile(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleAuthClick = () => {
    if (isAuthenticated) {
      setShowUserProfile(!showUserProfile);
    } else {
      setShowAuthModal(true);
    }
  };

  return (
    <>
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-semibold text-indigo-600">
                Baruch Study Rooms
              </h1>
            </div>
            
            <div className="flex items-center space-x-4">
              {isLoading ? (
                <div className="h-8 w-20 bg-gray-200 rounded animate-pulse"></div>
              ) : (
                <div className="relative" ref={profileRef}>
                  <button
                    onClick={handleAuthClick}
                    className="flex items-center space-x-2 px-4 py-2 text-sm font-medium text-gray-700 hover:text-indigo-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 rounded-md"
                  >
                    {isAuthenticated ? (
                      <>
                        <div className="w-8 h-8 bg-indigo-600 rounded-full flex items-center justify-center">
                          <span className="text-white text-sm font-medium">
                            {user?.firstName?.[0]}{user?.lastName?.[0]}
                          </span>
                        </div>
                        <span className="hidden sm:block">{user?.firstName}</span>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </>
                    ) : (
                      <>
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                        <span>Sign In</span>
                      </>
                    )}
                  </button>
                  
                  {showUserProfile && isAuthenticated && (
                    <UserProfile onClose={() => setShowUserProfile(false)} />
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        initialMode="login"
      />
    </>
  );
};

export default Header;
