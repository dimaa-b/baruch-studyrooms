import './App.css'

function App() {
  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="max-w-md mx-auto bg-white rounded-xl shadow-md overflow-hidden">
        <div className="p-8">
          <div className="uppercase tracking-wide text-sm text-indigo-500 font-semibold">
            Baruch Study Rooms
          </div>
          <h1 className="block mt-1 text-lg leading-tight font-medium text-black">
            Welcome to the Study Room Booking System
          </h1>
          <p className="mt-2 text-gray-500">
            Find and book study rooms for your academic needs.
          </p>
          <button className="mt-4 bg-indigo-500 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded">
            Get Started
          </button>
        </div>
      </div>
    </div>
  )
}

export default App
