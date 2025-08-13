import { useState } from 'react';
import AuthModal from './AuthModal';

const LandingPage = () => {
    const [showAuthModal, setShowAuthModal] = useState(false);

    return (
        <div className="bg-[#1B38E2] w-full min-h-screen h-full text-white fixed inset-0 overflow-y-auto">
            {/* Hero Section */}
            <div className="flex items-center justify-center min-h-screen">
                <div className="container mx-auto px-6 py-16">
                    <div className="text-center mb-16 mt-25">
                        <h1 className="text-5xl md:text-6xl font-black mb-6 font-royal">
                            baruch study room booker
                        </h1>

                        <div className="flex flex-col sm:flex-row gap-4 justify-center">
                            <button onClick={() => setShowAuthModal(true)} className="bg-white text-[#1B38E2] px-8 py-3 rounded-lg font-bold text-lg hover:bg-gray-100 transition-colors font-royal">
                                get started
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <AuthModal
                isOpen={showAuthModal}
                onClose={() => setShowAuthModal(false)}
                initialMode="register"
            />
        </div>
    )
}

export default LandingPage