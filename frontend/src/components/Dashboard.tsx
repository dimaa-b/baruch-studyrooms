import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import Header from './Header';

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

interface Booking {
  id: string;
  roomName: string;
  date: string;
  time: string;
  duration: string;
  status: 'confirmed' | 'pending' | 'cancelled';
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

    // Mock booking data - replace with actual API calls

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

    // Handle slot selection for booking - find any available room at the selected time
    const handleSlotClick = (slotIndex: number, displayTime: string) => {
        // Find the first available room at this time slot
        const roomIds = Object.keys(availabilityData);
        for (const roomId of roomIds) {
            const slot = availabilityData[roomId][slotIndex];
            if (slot && slot.available) {
                setSelectedSlot({ roomId, slot });
                // Convert display time to 24-hour format for the time selector
                const time24 = convertTo24Hour(slot.displayTime);
                setSelectedTime(time24);
                break;
            }
        }
    };

    // Helper function to convert display time to 24-hour format
    const convertTo24Hour = (displayTime: string) => {
        const match = displayTime.match(/(\d{1,2}):(\d{2})\s*(AM|PM)/i);
        if (!match) return '09:00';
        
        let [, hours, minutes, period] = match;
        let hour24 = parseInt(hours);
        
        if (period.toUpperCase() === 'PM' && hour24 !== 12) {
            hour24 += 12;
        } else if (period.toUpperCase() === 'AM' && hour24 === 12) {
            hour24 = 0;
        }
        
        return `${hour24.toString().padStart(2, '0')}:${minutes}`;
    };

    // Get all unique time slots for the grid header
    const getTimeSlots = () => {
        const roomIds = Object.keys(availabilityData);
        if (roomIds.length === 0) return [];
        return availabilityData[roomIds[0]]?.map(slot => slot.displayTime) || [];
    };

    // Get consolidated availability - true if ANY room is available at that time
    const getConsolidatedAvailability = () => {
        const timeSlots = getTimeSlots();
        return timeSlots.map((timeSlot, index) => {
            const isAvailable = Object.values(availabilityData).some(roomSlots => 
                roomSlots[index]?.available
            );
            return {
                displayTime: timeSlot,
                available: isAvailable,
                slotIndex: index
            };
        });
    };

    const handleBookRoom = () => {
        if (selectedSlot) {
            console.log(`Booking room ${selectedSlot.roomId} for ${selectedDate} at ${selectedSlot.slot.displayTime} for ${selectedDuration} hour(s)`);
            console.log('Slot details:', selectedSlot.slot);
            alert(`Booking room ${selectedSlot.roomId} at ${selectedSlot.slot.displayTime}!`);
        } else {
            alert('Please select a time slot from the availability grid first!');
        }
    };

    return (
        <div className="bg-[#1B38E2] w-full min-h-screen text-black">
            <Header />
            
            {/* Main Content */}
            <div className="pt-24 px-4 sm:px-6 pb-8 mt-15">
                <div className="container mx-auto max-w-7xl">
                    {/* Welcome Section */}
                    <div className="mb-6 sm:mb-8">
                        <h1 className="text-3xl sm:text-4xl md:text-5xl font-ultra mb-4 text-white font-torque">
                            Welcome back, {user?.firstName}!
                        </h1>
                    </div>

                    {/* Quick Stats */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 sm:gap-6 mb-6 sm:mb-8">
                        <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-4 sm:p-6 border-2 border-black border-opacity-90">
                            <h3 className="text-base sm:text-lg font-bold mb-2 text-black font-torque">Total Rooms</h3>
                            <p className="text-2xl sm:text-3xl font-ultra text-black font-torque">{Object.keys(availabilityData).length}</p>
                        </div>
                        <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-4 sm:p-6 border-2 border-black border-opacity-90">
                            <h3 className="text-base sm:text-lg font-bold mb-2 text-black font-torque">Available Slots</h3>
                            <p className="text-2xl sm:text-3xl font-ultra text-black font-torque">
                                {Object.values(availabilityData).flat().filter(slot => slot.available).length}
                            </p>
                        </div>
                        <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-4 sm:p-6 border-2 border-black border-opacity-90">
                            <h3 className="text-base sm:text-lg font-bold mb-2 text-black font-torque">Your Bookings</h3>
                            <p className="text-2xl sm:text-3xl font-ultra text-black font-torque">{myBookings.length}</p>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 lg:gap-8">
                        {/* Booking Form */}
                        <div className="xl:col-span-1 order-2 xl:order-1"> 
                            <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-4 sm:p-6 border-2 border-black border-opacity-90 xl:sticky xl:top-24">
                                <h2 className="text-2xl font-bold mb-6 text-black font-torque">Book a Room</h2>
                                
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
                                    
                                    <button
                                        onClick={handleBookRoom}
                                        disabled={!selectedSlot}
                                        className={`w-full py-3 px-4 rounded-lg font-semibold transition-colors ${
                                            selectedSlot
                                                ? 'bg-white text-[#1B38E2] hover:bg-gray-100'
                                                : 'bg-gray-500 text-gray-300 cursor-not-allowed'
                                        }`}
                                    >
                                        {selectedSlot ? `Book Room ${selectedSlot.roomId}` : 'Select a Time Slot'}
                                    </button>
                                    
                                    {selectedSlot && (
                                        <div className="p-3 bg-blue-500 bg-opacity-20 rounded-lg border border-blue-500">
                                            <p className="text-black text-sm font-medium">
                                                Selected: Room {selectedSlot.roomId}
                                            </p>
                                            <p className="text-black text-sm">
                                                {selectedSlot.slot.displayTime} ({selectedDuration} hour{selectedDuration !== '1' ? 's' : ''})
                                            </p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Availability Grid */}
                        <div className="xl:col-span-2 order-1 xl:order-2">
                            <h2 className="text-xl sm:text-2xl font-bold mb-4 sm:mb-6 text-white font-torque">Room Availability</h2>
                            
                            {isLoading ? (
                                <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-8 border-2 border-black border-opacity-90">
                                    <div className="text-center text-white">Loading availability...</div>
                                </div>
                            ) : Object.keys(availabilityData).length > 0 ? (
                                <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-2 sm:p-4 border-2 border-black border-opacity-90 overflow-x-auto">
                                    <div className="w-full">
                                        {/* Grid Header */}
                                        <div className="grid grid-cols-[60px_1fr_1fr_1fr_1fr_1fr_1fr_1fr_1fr_1fr_1fr] gap-1 mb-1">
                                            <div className="text-xs font-semibold text-black p-1">Availability</div>
                                            {getTimeSlots().map((time, index) => (
                                                <div key={index} className="text-xs font-medium text-black p-1 text-center">
                                                    <span className="block sm:hidden">{time.replace(':00', '')}</span>
                                                    <span className="hidden sm:block">{time}</span>
                                                </div>
                                            ))}
                                        </div>
                                        
                                        {/* Consolidated Availability Row */}
                                        <div className="grid grid-cols-[60px_1fr_1fr_1fr_1fr_1fr_1fr_1fr_1fr_1fr_1fr] gap-1">
                                            <div className="text-xs font-medium text-black p-1 bg-white bg-opacity-20 rounded flex items-center">
                                                <span className="truncate">Any Room</span>
                                            </div>
                                            {getConsolidatedAvailability().map((consolidatedSlot, index) => (
                                                <button
                                                    key={index}
                                                    onClick={() => handleSlotClick(consolidatedSlot.slotIndex, consolidatedSlot.displayTime)}
                                                    disabled={!consolidatedSlot.available}
                                                    className={`p-0.5 sm:p-1 rounded text-xs font-medium transition-colors min-h-[20px] sm:min-h-[24px] touch-manipulation ${
                                                        consolidatedSlot.available
                                                            ? selectedSlot && getTimeSlots()[index] === selectedSlot.slot.displayTime
                                                                ? 'bg-blue-500 text-white border-2 border-blue-700'
                                                                : 'bg-green-500 text-white hover:bg-green-600 cursor-pointer active:bg-green-700'
                                                            : 'bg-red-500 text-white cursor-not-allowed opacity-75'
                                                    }`}
                                                    title={`${consolidatedSlot.displayTime} - ${consolidatedSlot.available ? 'Available' : 'No rooms available'}`}
                                                >
                                                    <span className="block">{consolidatedSlot.available ? '✓' : '✗'}</span>
                                                </button>
                                            ))}
                                        </div>
                                        
                                        {/* Legend */}
                                        <div className="mt-2 flex flex-wrap gap-2 sm:gap-3 text-xs">
                                            <div className="flex items-center gap-1">
                                                <div className="w-3 h-3 sm:w-4 sm:h-4 bg-green-500 rounded"></div>
                                                <span className="text-black">Available</span>
                                            </div>
                                            <div className="flex items-center gap-1">
                                                <div className="w-3 h-3 sm:w-4 sm:h-4 bg-red-500 rounded"></div>
                                                <span className="text-black">Occupied</span>
                                            </div>
                                            <div className="flex items-center gap-1">
                                                <div className="w-3 h-3 sm:w-4 sm:h-4 bg-blue-500 border-2 border-blue-700 rounded"></div>
                                                <span className="text-black">Selected</span>
                                            </div>
                                        </div>
                                        
                                        {/* Mobile Instructions */}
                                        <div className="mt-2 sm:hidden">
                                            <p className="text-xs text-gray-700 text-center">
                                                Tap time slots to select them
                                            </p>
                                        </div>
                                        
                                        {selectedSlot && (
                                            <div className="mt-3 p-3 bg-blue-500 bg-opacity-20 rounded-lg border border-blue-500">
                                                <p className="text-black font-medium text-sm">
                                                    Selected: Room {selectedSlot.roomId} at {selectedSlot.slot.displayTime}
                                                </p>
                                                <p className="text-gray-700 text-xs">
                                                    {selectedSlot.slot.start} - {selectedSlot.slot.end}
                                                </p>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ) : (
                                <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-8 border-2 border-black border-opacity-90">
                                    <div className="text-center text-black">
                                        <p className="text-lg mb-2">No availability data found</p>
                                        <p className="text-sm text-gray-700">Please select a different date or try again later.</p>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* My Bookings Section */}
                    <div className="mt-8 sm:mt-12">
                        <h2 className="text-xl sm:text-2xl font-bold mb-4 sm:mb-6 text-white font-torque">My Bookings</h2>
                        
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
                            {myBookings.map((booking) => (
                                <div
                                    key={booking.id}
                                    className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-4 sm:p-6 border-2 border-black border-opacity-90"
                                >
                                    <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start mb-4 gap-3">
                                        <div className="flex-1">
                                            <h3 className="text-base sm:text-lg font-bold mb-2 text-black font-torque">{booking.roomName}</h3>
                                            <p className="text-sm text-gray-700 font-medium">{booking.date}</p>
                                            <p className="text-sm text-gray-700 font-medium">🕐 {booking.time} • {booking.duration}</p>
                                        </div>
                                        <span className={`px-3 py-1 rounded-full text-xs sm:text-sm font-medium self-start ${
                                            booking.status === 'confirmed'
                                                ? 'bg-green-500 text-white'
                                                : booking.status === 'pending'
                                                ? 'bg-yellow-500 text-white'
                                                : 'bg-red-500 text-white'
                                        }`}>
                                            {booking.status.charAt(0).toUpperCase() + booking.status.slice(1)}
                                        </span>
                                    </div>
                                    
                                    <div className="flex flex-col sm:flex-row gap-2">
                                        <button className="flex-1 py-2 px-4 rounded-lg font-semibold text-sm bg-white bg-opacity-20 hover:bg-opacity-30 transition-colors">
                                            Modify
                                        </button>
                                        <button className="flex-1 py-2 px-4 rounded-lg font-semibold text-sm bg-red-500 hover:bg-red-600 transition-colors text-white">
                                            Cancel
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                        
                        {myBookings.length === 0 && (
                            <div className="text-center py-8 sm:py-12">
                                <p className="text-gray-700 text-base sm:text-lg">No bookings yet. Book your first study room above!</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}

export default Dashboard