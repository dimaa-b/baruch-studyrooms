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
      {/* Floating Header */}
      <div className="fixed top-6 left-1/2 transform -translate-x-1/2 z-50 w-11/12 max-w-5xl">
        <header className="bg-gray-100 backdrop-blur-md bg-opacity-90 rounded-full shadow-lg border border-gray-200">
          <div className="px-8 py-4">
            <div className="flex justify-between items-center">
              {/* Logo/Brand */}
              <div className="flex items-center">
                <h1 className="text-2xl font-bold text-black tracking-tight">
                  baruch study rooms
                </h1>
              </div>
              
              {/* Auth Section */}
              <div className="flex items-center space-x-4">
                {isLoading ? (
                  <div className="h-8 w-20 bg-gray-200 rounded-full animate-pulse"></div>
                ) : (
                  <div className="relative" ref={profileRef}>
                    <button
                      onClick={handleAuthClick}
                      className="flex items-center space-x-2 px-4 py-2 text-sm font-medium text-black hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-2 rounded-full transition-colors duration-200"
                    >
                      {isAuthenticated ? (
                        <>
                          <div className="w-8 h-8 bg-black rounded-full flex items-center justify-center">
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
      </div>
      
      {/* Spacer to prevent content from being hidden under floating header */}

      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        initialMode="login"
      />
    </>
  );
};

export default Header;
