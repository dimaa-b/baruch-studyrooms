import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import Header from './Header';

interface StudyRoom {
  id: string;
  name: string;
  capacity: number;
  location: string;
  amenities: string[];
  isAvailable: boolean;
  nextAvailable?: string;
}

interface Booking {
  id: string;
  roomName: string;
  date: string;
  time: string;
  duration: string;
  status: 'confirmed' | 'pending' | 'cancelled';
}

interface TimeSlot {
  available: boolean;
  checksum: string;
  displayTime: string;
  end: string;
  itemId: number;
  start: string;
  className?: string;
}

interface AvailabilityData {
  [roomId: string]: TimeSlot[];
}

const Dashboard = () => {
    const { user } = useAuth();
    const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
    const [selectedTime, setSelectedTime] = useState('09:00');
    const [selectedDuration, setSelectedDuration] = useState('1');
    const [searchTerm, setSearchTerm] = useState('');
    const [availabilityData, setAvailabilityData] = useState<AvailabilityData>({});
    const [selectedSlot, setSelectedSlot] = useState<{roomId: string, slot: TimeSlot} | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    // Mock data - replace with actual API calls
    const studyRooms: StudyRoom[] = [
        {
            id: '1',
            name: 'Newman Library - Study Room A',
            capacity: 4,
            location: 'Newman Library, 2nd Floor',
            amenities: ['Whiteboard', 'Power Outlets', 'WiFi', 'Projector'],
            isAvailable: true,
        },
        {
            id: '2',
            name: 'Newman Library - Study Room B',
            capacity: 6,
            location: 'Newman Library, 2nd Floor',
            amenities: ['Whiteboard', 'Power Outlets', 'WiFi'],
            isAvailable: true,
        },
        {
            id: '3',
            name: 'Vertical Campus - Group Study Room',
            capacity: 8,
            location: 'Vertical Campus, 3rd Floor',
            amenities: ['Large Table', 'Power Outlets', 'WiFi', 'TV Screen'],
            isAvailable: false,
            nextAvailable: '2:00 PM',
        },
        {
            id: '4',
            name: 'Library Building - Quiet Study',
            capacity: 2,
            location: 'Library Building, 1st Floor',
            amenities: ['Quiet Zone', 'Power Outlets', 'WiFi'],
            isAvailable: true,
        },
    ];

    const myBookings: Booking[] = [
        {
            id: '1',
            roomName: 'Newman Library - Study Room A',
            date: '2025-06-22',
            time: '2:00 PM',
            duration: '2 hours',
            status: 'confirmed',
        },
        {
            id: '2',
            roomName: 'Vertical Campus - Group Study Room',
            date: '2025-06-23',
            time: '10:00 AM',
            duration: '1 hour',
            status: 'pending',
        },
    ];

    const filteredRooms = studyRooms.filter(room =>
        room.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        room.location.toLowerCase().includes(searchTerm.toLowerCase())
    );

    // Fetch availability data from API
    const fetchAvailability = async (date: string) => {
        setIsLoading(true);
        try {
            const response = await fetch(`http://localhost:5001/api/availability?date=${date}`);
            if (response.ok) {
                const data = await response.json();
                setAvailabilityData(data);
            }
        } catch (error) {
            console.error('Error fetching availability:', error);
        } finally {
            setIsLoading(false);
        }
    };

    // Fetch availability when component mounts or date changes
    useEffect(() => {
        fetchAvailability(selectedDate);
    }, [selectedDate]);

    // Handle slot selection for booking
    const handleSlotClick = (roomId: string, slot: TimeSlot) => {
        if (slot.available) {
            setSelectedSlot({ roomId, slot });
            // Update the booking form with selected time
            setSelectedTime(slot.displayTime.replace(/[^\d:]/g, '').padStart(5, '0'));
        }
    };

    // Get all unique time slots for the grid header
    const getTimeSlots = () => {
        const roomIds = Object.keys(availabilityData);
        if (roomIds.length === 0) return [];
        return availabilityData[roomIds[0]]?.map(slot => slot.displayTime) || [];
    };

    const handleBookRoom = (roomId: string) => {
        // Handle room booking logic
        console.log(`Booking room ${roomId} for ${selectedDate} at ${selectedTime} for ${selectedDuration} hour(s)`);
        alert('Booking functionality will be implemented!');
    };

    return (
        <div className="bg-[#1B38E2] w-full min-h-screen text-black">
            <Header />
            
            {/* Main Content */}
            <div className="pt-24 px-6 pb-8 mt-15">
                <div className="container mx-auto max-w-7xl">
                    {/* Welcome Section */}
                    <div className="mb-8">
                        <h1 className="text-4xl md:text-5xl font-bold mb-4 text-white">
                            Welcome back, {user?.firstName}!
                        </h1>
                    </div>

                    {/* Quick Stats */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                        <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-6 border-2 border-black border-opacity-90">
                            <h3 className="text-lg font-semibold mb-2 text-black">Available Rooms</h3>
                            <p className="text-3xl font-bold text-black">{studyRooms.filter(room => room.isAvailable).length}</p>
                        </div>
                        <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-6 border-2 border-black border-opacity-90">
                            <h3 className="text-lg font-semibold mb-2 text-black">Your Bookings</h3>
                            <p className="text-3xl font-bold text-black">{myBookings.length}</p>
                        </div>
                        <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-6 border-2 border-black border-opacity-90">
                            <h3 className="text-lg font-semibold mb-2 text-black">Hours Booked</h3>
                            <p className="text-3xl font-bold text-black">5</p>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                        {/* Booking Form */}
                        <div className="lg:col-span-1"> 
                            <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-6 border-2 border-black border-opacity-90 sticky top-24">
                                <h2 className="text-2xl font-bold mb-6 text-black">Book a Room</h2>
                                
                                <div className="space-y-4">
                                    <div>
                                        <label className="block text-sm font-medium mb-2 text-black">Date</label>
                                        <input
                                            type="date"
                                            value={selectedDate}
                                            onChange={(e) => setSelectedDate(e.target.value)}
                                            className="w-full px-4 py-2 rounded-lg bg-white bg-opacity-20 border border-white border-opacity-30 text-black placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-white focus:ring-opacity-50"
                                        />
                                    </div>
                                    
                                    <div>
                                        <label className="block text-sm font-medium mb-2 text-black">Time</label>
                                        <select
                                            value={selectedTime}
                                            onChange={(e) => setSelectedTime(e.target.value)}
                                            className="w-full px-4 py-2 rounded-lg bg-white bg-opacity-20 border border-white border-opacity-30 text-black focus:outline-none focus:ring-2 focus:ring-white focus:ring-opacity-50"
                                        >
                                            <option value="09:00">9:00 AM</option>
                                            <option value="10:00">10:00 AM</option>
                                            <option value="11:00">11:00 AM</option>
                                            <option value="12:00">12:00 PM</option>
                                            <option value="13:00">1:00 PM</option>
                                            <option value="14:00">2:00 PM</option>
                                            <option value="15:00">3:00 PM</option>
                                            <option value="16:00">4:00 PM</option>
                                            <option value="17:00">5:00 PM</option>
                                        </select>
                                    </div>
                                    
                                    <div>
                                        <label className="block text-sm font-medium mb-2 text-black">Duration</label>
                                        <select
                                            value={selectedDuration}
                                            onChange={(e) => setSelectedDuration(e.target.value)}
                                            className="w-full px-4 py-2 rounded-lg bg-white bg-opacity-20 border border-white border-opacity-30 text-black focus:outline-none focus:ring-2 focus:ring-white focus:ring-opacity-50"
                                        >
                                            <option value="1">1 hour</option>
                                            <option value="2">2 hours</option>
                                            <option value="3">3 hours</option>
                                            <option value="4">4 hours</option>
                                        </select>
                                    </div>
                                    
                                    <div>
                                        <label className="block text-sm font-medium mb-2 text-black">Search Rooms</label>
                                        <input
                                            type="text"
                                            placeholder="Search by name or location..."
                                            value={searchTerm}
                                            onChange={(e) => setSearchTerm(e.target.value)}
                                            className="w-full px-4 py-2 rounded-lg bg-white bg-opacity-20 border border-white border-opacity-30 text-black placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-white focus:ring-opacity-50"
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Available Rooms */}
                        <div className="lg:col-span-2">
                            <h2 className="text-2xl font-bold mb-6 text-white">Available Study Rooms</h2>
                            
                            <div className="space-y-4">
                                {filteredRooms.map((room) => (
                                    <div
                                        key={room.id}
                                        className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-6 border-2 border-black border-opacity-90"
                                    >
                                        <div className="flex justify-between items-start mb-4">
                                            <div>
                                                <h3 className="text-xl font-semibold mb-2 text-black">{room.name}</h3>
                                                <p className="text-gray-700 mb-2">📍 {room.location}</p>
                                                <p className="text-gray-700 mb-2">👥 Capacity: {room.capacity} people</p>
                                            </div>
                                            <div className="text-right">
                                                {room.isAvailable ? (
                                                    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-500 text-white">
                                                        Available
                                                    </span>
                                                ) : (
                                                    <div>
                                                        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-500 text-white mb-2">
                                                            Occupied
                                                        </span>
                                                        {room.nextAvailable && (
                                                            <p className="text-sm text-gray-700">Next available: {room.nextAvailable}</p>
                                                        )}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                        
                                        <div className="mb-4">
                                            <h4 className="text-sm font-medium mb-2 text-black">Amenities:</h4>
                                            <div className="flex flex-wrap gap-2">
                                                {room.amenities.map((amenity, index) => (
                                                    <span
                                                        key={index}
                                                        className="px-2 py-1 bg-white bg-opacity-20 rounded-md text-sm text-black"
                                                    >
                                                        {amenity}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                        
                                        <button
                                            onClick={() => handleBookRoom(room.id)}
                                            disabled={!room.isAvailable}
                                            className={`w-full py-2 px-4 rounded-lg font-semibold transition-colors ${
                                                room.isAvailable
                                                    ? 'bg-white text-[#1B38E2] hover:bg-gray-100'
                                                    : 'bg-gray-500 text-gray-300 cursor-not-allowed'
                                            }`}
                                        >
                                            {room.isAvailable ? 'Book This Room' : 'Not Available'}
                                        </button>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* My Bookings Section */}
                    <div className="mt-12">
                        <h2 className="text-2xl font-bold mb-6 text-black">My Bookings</h2>
                        
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            {myBookings.map((booking) => (
                                <div
                                    key={booking.id}
                                    className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-6 border-2 border-black border-opacity-90"
                                >
                                    <div className="flex justify-between items-start mb-4">
                                        <div>
                                            <h3 className="text-lg font-semibold mb-2 text-black">{booking.roomName}</h3>
                                            <p className="text-gray-700">📅 {booking.date}</p>
                                            <p className="text-gray-700">🕐 {booking.time} • {booking.duration}</p>
                                        </div>
                                        <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                                            booking.status === 'confirmed'
                                                ? 'bg-green-500 text-white'
                                                : booking.status === 'pending'
                                                ? 'bg-yellow-500 text-white'
                                                : 'bg-red-500 text-white'
                                        }`}>
                                            {booking.status.charAt(0).toUpperCase() + booking.status.slice(1)}
                                        </span>
                                    </div>
                                    
                                    <div className="flex gap-2">
                                        <button className="flex-1 py-2 px-4 rounded-lg font-semibold bg-white bg-opacity-20 hover:bg-opacity-30 transition-colors">
                                            Modify
                                        </button>
                                        <button className="flex-1 py-2 px-4 rounded-lg font-semibold bg-red-500 hover:bg-red-600 transition-colors">
                                            Cancel
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                        
                        {myBookings.length === 0 && (
                            <div className="text-center py-12">
                                <p className="text-gray-700 text-lg">No bookings yet. Book your first study room above!</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}

export default Dashboard