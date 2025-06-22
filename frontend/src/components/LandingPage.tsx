const LandingPage = () => {
    return (
        <div className="bg-[#1B38E2] w-full min-h-screen h-full text-white fixed inset-0 overflow-y-auto">
            {/* Hero Section */}
            <div className="container mx-auto px-6 py-16">
                <div className="text-center mb-16 mt-25">
                    <h1 className="text-5xl md:text-6xl font-bold mb-6">
                        baruch study room booker
                    </h1>

                    <div className="flex flex-col sm:flex-row gap-4 justify-center">
                        <button className="bg-white text-[#1B38E2] px-8 py-3 rounded-lg font-semibold text-lg hover:bg-gray-100 transition-colors">
                            get started
                        </button>
                    </div>
                </div>

                {/* Features Section */}
                <div className="grid md:grid-cols-3 gap-8 mb-16">
                    <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 text-center">
                        <div className="w-16 h-16 bg-white/20 rounded-full flex items-center justify-center mx-auto mb-4">
                            <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z" clipRule="evenodd" />
                            </svg>
                        </div>
                        <h3 className="text-xl font-semibold mb-3">Easy Booking</h3>
                        <p className="opacity-90">
                            Browse available study rooms and book them instantly with just a few clicks.
                        </p>
                    </div>

                    <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 text-center">
                        <div className="w-16 h-16 bg-white/20 rounded-full flex items-center justify-center mx-auto mb-4">
                            <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                            </svg>
                        </div>
                        <h3 className="text-xl font-semibold mb-3">Real-Time Availability</h3>
                        <p className="opacity-90">
                            See live room availability and get instant confirmations for your bookings.
                        </p>
                    </div>

                    <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 text-center">
                        <div className="w-16 h-16 bg-white/20 rounded-full flex items-center justify-center mx-auto mb-4">
                            <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </div>
                        <h3 className="text-xl font-semibold mb-3">Secure Access</h3>
                        <p className="opacity-90">
                            Login with your Baruch/CUNY credentials for secure and personalized access.
                        </p>
                    </div>
                </div>

                {/* How It Works Section */}
                <div className="bg-white/5 backdrop-blur-sm rounded-2xl p-8 mb-16">
                    <h2 className="text-3xl font-bold text-center mb-12">How It Works</h2>
                    <div className="grid md:grid-cols-4 gap-8">
                        <div className="text-center">
                            <div className="w-12 h-12 bg-white text-[#1B38E2] rounded-full flex items-center justify-center mx-auto mb-4 font-bold text-xl">
                                1
                            </div>
                            <h3 className="text-lg font-semibold mb-2">Sign Up</h3>
                            <p className="opacity-90 text-sm">
                                Create an account using your Baruch/CUNY email address
                            </p>
                        </div>
                        <div className="text-center">
                            <div className="w-12 h-12 bg-white text-[#1B38E2] rounded-full flex items-center justify-center mx-auto mb-4 font-bold text-xl">
                                2
                            </div>
                            <h3 className="text-lg font-semibold mb-2">Browse Rooms</h3>
                            <p className="opacity-90 text-sm">
                                View available study rooms and their time slots
                            </p>
                        </div>
                        <div className="text-center">
                            <div className="w-12 h-12 bg-white text-[#1B38E2] rounded-full flex items-center justify-center mx-auto mb-4 font-bold text-xl">
                                3
                            </div>
                            <h3 className="text-lg font-semibold mb-2">Book & Confirm</h3>
                            <p className="opacity-90 text-sm">
                                Select your preferred time and confirm your booking
                            </p>
                        </div>
                        <div className="text-center">
                            <div className="w-12 h-12 bg-white text-[#1B38E2] rounded-full flex items-center justify-center mx-auto mb-4 font-bold text-xl">
                                4
                            </div>
                            <h3 className="text-lg font-semibold mb-2">Study!</h3>
                            <p className="opacity-90 text-sm">
                                Enjoy your reserved study space and be productive
                            </p>
                        </div>
                    </div>
                </div>

                {/* Requirements Section */}
                <div className="bg-white/5 backdrop-blur-sm rounded-2xl p-8">
                    <h2 className="text-2xl font-bold text-center mb-8">Requirements</h2>
                    <div className="max-w-2xl mx-auto">
                        <div className="space-y-4">
                            <div className="flex items-center gap-3">
                                <div className="w-6 h-6 bg-green-500 rounded-full flex items-center justify-center flex-shrink-0">
                                    <svg className="w-4 h-4" fill="white" viewBox="0 0 20 20">
                                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                    </svg>
                                </div>
                                <span>Valid Baruch College or CUNY SPS email address</span>
                            </div>
                            <div className="flex items-center gap-3">
                                <div className="w-6 h-6 bg-green-500 rounded-full flex items-center justify-center flex-shrink-0">
                                    <svg className="w-4 h-4" fill="white" viewBox="0 0 20 20">
                                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                    </svg>
                                </div>
                                <span>Current student status at Baruch or CUNY SPS</span>
                            </div>
                            <div className="flex items-center gap-3">
                                <div className="w-6 h-6 bg-green-500 rounded-full flex items-center justify-center flex-shrink-0">
                                    <svg className="w-4 h-4" fill="white" viewBox="0 0 20 20">
                                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                    </svg>
                                </div>
                                <span>Agree to follow library study room policies</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

export default LandingPage