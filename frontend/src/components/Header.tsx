import { useState, useRef, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import AuthModal from './AuthModal';
import UserProfile from './UserProfile';

const Header = () => {
  const { user, isAuthenticated, isLoading } = useAuth();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showUserProfile, setShowUserProfile] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setShowUserProfile(false);
      }
    };

    const handleScroll = () => {
      const scrollPosition = window.scrollY;
      setIsScrolled(scrollPosition > 50);
    };

    document.addEventListener('mousedown', handleClickOutside);
    window.addEventListener('scroll', handleScroll);
    
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      window.removeEventListener('scroll', handleScroll);
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
      <div className={`fixed left-1/2 transform -translate-x-1/2 z-50 w-11/12 max-w-5xl transition-all duration-300 ease-in-out ${
        isScrolled ? 'top-2' : 'top-6'
      }`}>
        <header className={`bg-gray-100 backdrop-blur-md bg-opacity-90 rounded-full shadow-lg border-2 border-black transition-all duration-300 ease-in-out ${
          isScrolled ? 'scale-90' : 'scale-100'
        }`}>
          <div className={`px-8 transition-all duration-300 ease-in-out ${
            isScrolled ? 'py-2' : 'py-4'
          }`}>
            <div className="flex justify-between items-center">
              {/* Logo/Brand */}
              <div className="flex items-center">
                <h1 className={`font-black text-black tracking-tight font-royal transition-all duration-300 ease-in-out ${
                  isScrolled ? 'text-lg' : 'text-2xl'
                }`}>
                  baruch study rooms
                </h1>
              </div>
              
              {/* Auth Section */}
              <div className="flex items-center space-x-4">
                {isLoading ? (
                  <div className={`bg-gray-200 rounded-full animate-pulse transition-all duration-300 ease-in-out ${
                    isScrolled ? 'h-6 w-16' : 'h-8 w-20'
                  }`}></div>
                ) : (
                  <div className="relative" ref={profileRef}>
                    <button
                      onClick={handleAuthClick}
                      className={`flex items-center space-x-2 px-4 text-sm font-medium text-black hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-2 rounded-full transition-all duration-300 ease-in-out font-royal ${
                        isScrolled ? 'py-1' : 'py-2'
                      }`}
                    >
                      {isAuthenticated ? (
                        <>
                          <div className={`bg-black rounded-full flex items-center justify-center transition-all duration-300 ease-in-out ${
                            isScrolled ? 'w-6 h-6' : 'w-8 h-8'
                          }`}>
                            <span className={`text-white font-medium transition-all duration-300 ease-in-out ${
                              isScrolled ? 'text-xs' : 'text-sm'
                            }`}>
                              {user?.firstName?.[0]}{user?.lastName?.[0]}
                            </span>
                          </div>
                          <span className="hidden sm:block">{user?.firstName}</span>
                          <svg className={`transition-all duration-300 ease-in-out ${
                            isScrolled ? 'w-3 h-3' : 'w-4 h-4'
                          }`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
