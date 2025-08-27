import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { API_BASE_URL } from '../config';
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

interface MonitoringRequest {
  request_id: string;
  target_date: string;
  start_time: string;
  end_time: string;
  duration_hours?: number;
  status: 'active' | 'completed' | 'stopped' | 'expired' | 'error';
  created_at: string;
  check_count?: number;
  first_name?: string;
  last_name?: string;
  email?: string;
  room_preference?: string;
  success_details?: {
    slots: any[];
    booking_id: string;
    booked_at: string;
    slot_count: number;
  };
  error_message?: string;
}

const Dashboard = () => {
    const { user } = useAuth();
    const bookingFormRef = useRef<HTMLDivElement>(null);
    const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
    const [selectedTime, setSelectedTime] = useState('09:00');
    const [selectedDuration, setSelectedDuration] = useState('1');
    const [availabilityData, setAvailabilityData] = useState<AvailabilityData>({});
    const [selectedSlot, setSelectedSlot] = useState<{roomId: string, slot: TimeSlot} | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isBooking, setIsBooking] = useState(false);
    const [monitoringRequests, setMonitoringRequests] = useState<MonitoringRequest[]>([]);
    const [isLoadingBookings, setIsLoadingBookings] = useState(false);
    const [showIndividualRooms, setShowIndividualRooms] = useState(false);

    // Fetch monitoring requests from API
    const fetchMonitoringRequests = async () => {
        setIsLoadingBookings(true);
        try {
            const response = await fetch(`${API_BASE_URL}/api/monitoring/list`, {
                credentials: 'include', // Include cookies for authentication
            });
            if (response.ok) {
                const data = await response.json();
                console.log('Monitoring requests data:', data);
                setMonitoringRequests(data.requests || []);
            } else {
                console.error('Failed to fetch monitoring requests:', response.status, response.statusText);
                setMonitoringRequests([]);
            }
        } catch (error) {
            console.error('Error fetching monitoring requests:', error);
            setMonitoringRequests([]);
        } finally {
            setIsLoadingBookings(false);
        }
    };

    // Fetch availability data from API
    const fetchAvailability = async (date: string) => {
        setIsLoading(true);
        try {
            const response = await fetch(`${API_BASE_URL}/api/availability?date=${date}`);
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

    // Fetch monitoring requests when component mounts
    useEffect(() => {
        fetchMonitoringRequests();
    }, []);

    // Re-evaluate selected slot when duration changes
    useEffect(() => {
        if (selectedSlot) {
            const timeSlots = getTimeSlots();
            const selectedSlotIndex = timeSlots.findIndex(slot => slot === selectedSlot.slot.displayTime);
            
            if (selectedSlotIndex !== -1) {
                // Check if the new duration is still valid for the current selection
                handleSlotClick(selectedSlotIndex, selectedSlot.slot.displayTime);
            }
        }
    }, [selectedDuration, availabilityData]);

    // Convert monitoring request to display format
    const formatMonitoringRequestForDisplay = (request: MonitoringRequest) => {
        const startTime = request.start_time;
        const endTime = request.end_time;
        
        // Convert 24-hour time to 12-hour display format
        const formatTime = (time: string) => {
            const [hours, minutes] = time.split(':');
            let hour = parseInt(hours);
            const period = hour >= 12 ? 'PM' : 'AM';
            
            if (hour === 0) hour = 12;
            else if (hour > 12) hour -= 12;
            
            return `${hour}:${minutes} ${period}`;
        };

        const displayTime = `${formatTime(startTime)} - ${formatTime(endTime)}`;
        
        // Calculate duration from start and end times if duration_hours is not available
        let duration = 'Unknown';
        if (request.duration_hours) {
            duration = `${request.duration_hours} hour${request.duration_hours !== 1 ? 's' : ''}`;
        } else if (startTime && endTime) {
            const start = new Date(`1970-01-01T${startTime}:00`);
            const end = new Date(`1970-01-01T${endTime}:00`);
            const diffHours = (end.getTime() - start.getTime()) / (1000 * 60 * 60);
            duration = `${diffHours} hour${diffHours !== 1 ? 's' : ''}`;
        }
        
        let displayStatus: 'confirmed' | 'pending' | 'cancelled';
        let roomName = 'Study Room';
        
        if (request.status === 'completed' && request.success_details?.booking_id) {
            displayStatus = 'confirmed';
            // Extract room info if available
            if (request.success_details.slots && request.success_details.slots.length > 0) {
                const roomId = request.success_details.slots[0].itemId;
                roomName = `Study Room ${roomId}`;
            }
        } else if (request.status === 'active') {
            displayStatus = 'pending';
            roomName = `Monitoring for Room ${request.room_preference || 'Any'}`;
        } else {
            displayStatus = 'cancelled';
            roomName = `Request ${request.status}`;
        }

        return {
            id: request.request_id,
            roomName,
            date: request.target_date,
            time: displayTime,
            duration,
            status: displayStatus,
            monitoringRequest: request, // Keep reference to original request
        };
    };

    // Get all bookings (converted monitoring requests)
    const getAllBookings = () => {
        return monitoringRequests.map(formatMonitoringRequestForDisplay);
    };

    // Stop a monitoring request
    const stopMonitoringRequest = async (requestId: string) => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/monitoring/${requestId}/stop`, {
                method: 'POST',
                credentials: 'include',
            });
            
            if (response.ok) {
                alert('✅ Monitoring request stopped successfully!');
                // Refresh the monitoring requests
                fetchMonitoringRequests();
            } else {
                const error = await response.json();
                alert(`❌ Failed to stop monitoring request: ${error.error || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('Error stopping monitoring request:', error);
            alert('❌ Network error while stopping monitoring request. Please try again.');
        }
    };



    // Create a monitoring request
    const createMonitoringRequest = async () => {
        if (!user) {
            return;
        }

        setIsBooking(true);
        
        try {
            // Prepare monitoring data
            const monitoringData = {
                date: selectedDate,
                startTime: selectedTime + ':00', // Convert HH:MM to HH:MM:SS format
                duration: parseInt(selectedDuration),
                firstName: user.firstName,
                lastName: user.lastName,
                email: user.email
            };

            console.log('Creating monitoring request:', monitoringData);

            const response = await fetch(`${API_BASE_URL}/api/monitoring/create`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify(monitoringData)
            });

            const result = await response.json();

            if (response.ok && result.success) {
                // Refresh monitoring requests to see the new one
                fetchMonitoringRequests();
            } else {
                console.error('Failed to create monitoring request:', result.message || result.error);
            }
        } catch (error) {
            console.error('Error creating monitoring request:', error);
        } finally {
            setIsBooking(false);
        }
    };

    // Handle slot selection for booking - find any available room at the selected time
    const handleSlotClick = (slotIndex: number, _displayTime: string) => {
        const duration = parseInt(selectedDuration);
        const roomIds = Object.keys(availabilityData);
        
        // Find the first room that has the required consecutive slots available
        for (const roomId of roomIds) {
            let allSlotsAvailable = true;
            
            // Check if all required consecutive slots are available
            for (let i = 0; i < duration; i++) {
                const slot = availabilityData[roomId][slotIndex + i];
                if (!slot || !slot.available) {
                    allSlotsAvailable = false;
                    break;
                }
            }
            
            if (allSlotsAvailable) {
                const slot = availabilityData[roomId][slotIndex];
                setSelectedSlot({ roomId, slot });
                // Convert display time to 24-hour format for the time selector
                const time24 = convertTo24Hour(slot.displayTime);
                setSelectedTime(time24);
                
                // Scroll to booking form after a short delay to ensure state update
                setTimeout(() => {
                    if (bookingFormRef.current) {
                        bookingFormRef.current.scrollIntoView({ 
                            behavior: 'smooth', 
                            block: 'start' 
                        });
                    }
                }, 100);
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

    // Helper function to convert 24-hour time to 12-hour display format
    const convertToDisplayTime = (time24: string) => {
        const [hours, minutes] = time24.split(':');
        let hour = parseInt(hours);
        const period = hour >= 12 ? 'PM' : 'AM';
        
        if (hour === 0) hour = 12;
        else if (hour > 12) hour -= 12;
        
        return `${hour}:${minutes} ${period}`;
    };

    // Handle time dropdown change and select corresponding slot
    const handleTimeChange = (newTime: string) => {
        setSelectedTime(newTime);
        
        // Convert selected time to display format and find matching slot
        const displayTime = convertToDisplayTime(newTime);
        const timeSlots = getTimeSlots();
        const slotIndex = timeSlots.findIndex(slot => slot === displayTime);
        
        if (slotIndex !== -1) {
            const duration = parseInt(selectedDuration);
            const roomIds = Object.keys(availabilityData);
            
            // Find the first room that has the required consecutive slots available
            for (const roomId of roomIds) {
                let allSlotsAvailable = true;
                
                // Check if all required consecutive slots are available
                for (let i = 0; i < duration; i++) {
                    const slot = availabilityData[roomId][slotIndex + i];
                    if (!slot || !slot.available) {
                        allSlotsAvailable = false;
                        break;
                    }
                }
                
                if (allSlotsAvailable) {
                    const slot = availabilityData[roomId][slotIndex];
                    setSelectedSlot({ roomId, slot });
                    
                    // Scroll to booking form after a short delay to ensure state update
                    setTimeout(() => {
                        if (bookingFormRef.current) {
                            bookingFormRef.current.scrollIntoView({ 
                                behavior: 'smooth', 
                                block: 'start' 
                            });
                        }
                    }, 100);
                    break;
                }
            }
        } else {
            // Clear selection if time not found in availability
            setSelectedSlot(null);
        }
    };

    // Get all unique time slots for the grid header
    const getTimeSlots = () => {
        const roomIds = Object.keys(availabilityData);
        if (roomIds.length === 0) return [];
        return availabilityData[roomIds[0]]?.map(slot => slot.displayTime) || [];
    };

    // Get consolidated availability - true if ANY room is available at that time for the selected duration
    const getConsolidatedAvailability = () => {
        const timeSlots = getTimeSlots();
        const duration = parseInt(selectedDuration);
        
        return timeSlots.map((timeSlot, index) => {
            // Check if there are enough remaining slots for the selected duration
            const remainingSlots = timeSlots.length - index;
            if (remainingSlots < duration) {
                // Not enough slots remaining for this duration
                return {
                    displayTime: timeSlot,
                    available: false,
                    slotIndex: index
                };
            }
            
            // Check if there are enough consecutive slots for the selected duration
            const isAvailable = Object.values(availabilityData).some(roomSlots => {
                // Check if this room has all required consecutive slots available
                for (let i = 0; i < duration; i++) {
                    const slot = roomSlots[index + i];
                    if (!slot || !slot.available) {
                        return false;
                    }
                }
                return true;
            });
            
            return {
                displayTime: timeSlot,
                available: isAvailable,
                slotIndex: index
            };
        });
    };

    // Helper function to check if a slot is part of the current selection
    const isSlotSelected = (slotIndex: number) => {
        if (!selectedSlot) return false;
        
        const selectedSlotIndex = getTimeSlots().findIndex(slot => slot === selectedSlot.slot.displayTime);
        const duration = parseInt(selectedDuration);
        
        return slotIndex >= selectedSlotIndex && slotIndex < selectedSlotIndex + duration;
    };

    const handleBookRoom = async () => {
        // Allow booking even if no slot is selected
        if (!user) {
            return;
        }
        await createMonitoringRequest();
        setSelectedSlot(null);
    };

    return (
        <div className="bg-[#1B38E2] w-full min-h-screen text-black">
            <Header />
            
            {/* Main Content */}
            <div className="pt-24 px-4 sm:px-6 pb-8 mt-15">
                <div className="container mx-auto max-w-7xl">
                    {/* Welcome Section */}
                    <div className="mb-6 sm:mb-8">
                        <h1 className="text-3xl sm:text-4xl md:text-5xl font-black mb-4 text-white font-royal">
                            Welcome back, {user?.firstName}!
                        </h1>
                    </div>

                    {/* Quick Stats */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 sm:gap-6 mb-6 sm:mb-8">
                        <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-4 sm:p-6 border-2 border-black border-opacity-90">
                            <h3 className="text-base sm:text-lg font-bold mb-2 text-black font-royal">Available Times</h3>
                            <p className="text-2xl sm:text-3xl font-black text-black font-royal">{Object.values(availabilityData).flat().filter(slot => slot.available).length}</p>
                        </div>
                        <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-4 sm:p-6 border-2 border-black border-opacity-90">
                            <h3 className="text-base sm:text-lg font-bold mb-2 text-black font-royal">Available Slots</h3>
                            <p className="text-2xl sm:text-3xl font-black text-black font-royal">
                                {Object.values(availabilityData).flat().filter(slot => slot.available).length}
                            </p>
                        </div>
                        <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-4 sm:p-6 border-2 border-black border-opacity-90">
                            <h3 className="text-base sm:text-lg font-bold mb-2 text-black font-royal">Your Requests</h3>
                            <p className="text-2xl sm:text-3xl font-black text-black font-royal">{monitoringRequests.length}</p>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 lg:gap-8">
                        {/* Booking Form */}
                        <div ref={bookingFormRef} className="xl:col-span-1 order-2 xl:order-1"> 
                            <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-4 sm:p-6 border-2 border-black border-opacity-90 xl:sticky xl:top-24">
                                <h2 className="text-2xl font-bold mb-6 text-black font-royal">Book a Time Slot</h2>
                                
                                <div className="space-y-4">
                                    <div>
                                        <label className="block text-sm font-medium mb-2 text-black">Time</label>
                                        <select
                                            value={selectedTime}
                                            onChange={(e) => handleTimeChange(e.target.value)}
                                            className="w-full px-4 py-2 rounded-lg bg-white bg-opacity-20 border border-white border-opacity-30 text-black focus:outline-none focus:ring-2 focus:ring-white focus:ring-opacity-50"
                                        >
                                            {getTimeSlots().map((displayTime, index) => {
                                                const time24 = convertTo24Hour(displayTime);
                                                return (
                                                    <option key={index} value={time24}>
                                                        {displayTime}
                                                    </option>
                                                );
                                            })}
                                            {getTimeSlots().length === 0 && (
                                                <option value="">No times available</option>
                                            )}
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
                                        </select>
                                    </div>
                                    
                                    <div className="space-y-2">
                                        <button
                                            onClick={handleBookRoom}
                                            disabled={isBooking}
                                            className={`w-full py-3 px-4 rounded-lg font-semibold transition-colors ${
                                                !isBooking
                                                    ? 'bg-blue-400 text-white hover:bg-blue-500 border-2 border-black'
                                                    : 'bg-gray-500 text-gray-300 cursor-not-allowed'
                                            }`}
                                        >
                                            {isBooking 
                                                ? 'Booking...' 
                                                : 'Book'
                                            }
                                        </button>
                                    </div>
                                    
                                    {selectedSlot && (
                                        <div className="p-3 bg-blue-400 bg-opacity-20 rounded-lg border border-blue-500">
                                            <p className="text-black text-sm font-medium">
                                                Selected Time Slot
                                            </p>
                                            <p className="text-black text-sm">
                                                {(() => {
                                                    const startTime = selectedSlot.slot.displayTime;
                                                    const duration = parseInt(selectedDuration);
                                                    
                                                    // Calculate end time
                                                    const match = startTime.match(/(\d{1,2}):(\d{2})\s*(AM|PM)/i);
                                                    if (!match) return startTime;
                                                    
                                                    let [, hours, minutes, period] = match;
                                                    let hour24 = parseInt(hours);
                                                    
                                                    // Convert to 24-hour format
                                                    if (period.toUpperCase() === 'PM' && hour24 !== 12) {
                                                        hour24 += 12;
                                                    } else if (period.toUpperCase() === 'AM' && hour24 === 12) {
                                                        hour24 = 0;
                                                    }
                                                    
                                                    // Add duration hours
                                                    const endHour24 = hour24 + duration;
                                                    
                                                    // Convert back to 12-hour format for end time
                                                    let endHour12 = endHour24;
                                                    let endPeriod = 'AM';
                                                    
                                                    if (endHour24 >= 12) {
                                                        endPeriod = 'PM';
                                                        if (endHour24 > 12) {
                                                            endHour12 = endHour24 - 12;
                                                        }
                                                    }
                                                    if (endHour24 === 0) {
                                                        endHour12 = 12;
                                                    }
                                                    
                                                    const endTime = `${endHour12}:${minutes} ${endPeriod}`;
                                                    
                                                    return `${startTime} - ${endTime}`;
                                                })()}
                                            </p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Availability Grid */}
                        <div className="xl:col-span-2 order-1 xl:order-2">
                            <h2 className="text-xl sm:text-2xl font-bold mb-4 sm:mb-6 text-white font-royal">Time Availability</h2>
                            
                            {/* Date Selection */}
                            <div className="mb-4 sm:mb-6">
                                <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-3 sm:p-4 border-2 border-black border-opacity-90">
                                    <label className="block text-sm font-medium mb-2 text-black">Select Date</label>
                                    <div className="flex gap-2">
                                        <input
                                            type="date"
                                            value={selectedDate}
                                            onChange={(e) => setSelectedDate(e.target.value)}
                                            className="flex-1 px-4 py-2 rounded-lg bg-white bg-opacity-20 border border-white border-opacity-30 text-black focus:outline-none focus:ring-2 focus:ring-white focus:ring-opacity-50"
                                            min={new Date().toISOString().split('T')[0]}
                                        />
                                        <button
                                            onClick={() => {
                                                const tomorrow = new Date();
                                                tomorrow.setDate(tomorrow.getDate() + 1);
                                                setSelectedDate(tomorrow.toISOString().split('T')[0]);
                                            }}
                                            className="px-4 py-2 rounded-lg bg-blue-400 hover:bg-blue-500 text-white font-medium text-sm transition-colors border-2 border-black whitespace-nowrap"
                                        >
                                            Tomorrow
                                        </button>
                                    </div>
                                </div>
                            </div>
                            
                            {isLoading ? (
                                <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-8 border-2 border-black border-opacity-90">
                                    <div className="text-center text-white">Loading availability...</div>
                                </div>
                            ) : Object.keys(availabilityData).length > 0 ? (
                                <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-2 sm:p-4 border-2 border-black border-opacity-90">
                                    <div className="w-full">
                                        {/* Grid Header */}
                                        <div className="grid gap-1 mb-1" style={{ gridTemplateColumns: `80px repeat(${getTimeSlots().length}, minmax(0, 1fr))` }}>
                                            <div className="text-xs font-semibold text-black p-1">Availability</div>
                                            {getTimeSlots().map((time, index) => (
                                                <div key={index} className="text-xs font-medium text-black p-1 text-center">
                                                    <span className="block sm:hidden">{time.replace(':00', '')}</span>
                                                    <span className="hidden sm:block">{time}</span>
                                                </div>
                                            ))}
                                        </div>
                                        
                                        {/* Consolidated Availability Row */}
                                        <div className="grid gap-1" style={{ gridTemplateColumns: `80px repeat(${getTimeSlots().length}, minmax(0, 1fr))` }}>
                                            <div className="text-xs font-medium text-black p-1 bg-white bg-opacity-20 rounded flex items-center">
                                                <span className="truncate">Time Slots</span>
                                            </div>
                                            {getConsolidatedAvailability().map((consolidatedSlot, index) => (
                                                <button
                                                    key={index}
                                                    onClick={() => handleSlotClick(consolidatedSlot.slotIndex, consolidatedSlot.displayTime)}
                                                    disabled={!consolidatedSlot.available}
                                                    className={`p-1 sm:p-2 rounded text-xs font-medium transition-colors min-h-[28px] sm:min-h-[36px] w-full touch-manipulation ${
                                                        consolidatedSlot.available
                                                            ? isSlotSelected(consolidatedSlot.slotIndex)
                                                                ? 'bg-blue-500 text-white border-2 border-blue-700'
                                                                : 'bg-green-500 text-white hover:bg-green-600 cursor-pointer active:bg-green-700'
                                                            : 'bg-red-500 text-white cursor-not-allowed opacity-75'
                                                    }`}
                                                    title={`${consolidatedSlot.displayTime} - ${consolidatedSlot.available ? 'Available' : 'No availability'}`}
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
                                        
                                        {/* Mobile Instructions and Individual Rooms Toggle */}
                                        <div className="mt-2 sm:hidden">
                                            <p className="text-xs text-gray-700 text-center mb-2">
                                                Tap time slots to select them
                                            </p>
                                            <div className="flex justify-center">
                                                <button
                                                    onClick={() => setShowIndividualRooms(!showIndividualRooms)}
                                                    className="text-xs px-3 py-1 bg-white bg-opacity-20 hover:bg-opacity-30 rounded-lg text-black transition-colors"
                                                >
                                                    {showIndividualRooms ? 'Hide Individual Rooms' : 'See Individual Rooms'}
                                                </button>
                                            </div>
                                        </div>
                                        
                                        {/* Desktop Individual Rooms Toggle */}
                                        <div className="mt-2 hidden sm:block">
                                            <div className="flex justify-center">
                                                <button
                                                    onClick={() => setShowIndividualRooms(!showIndividualRooms)}
                                                    className="text-xs sm:text-sm px-3 py-1 bg-white bg-opacity-20 hover:bg-opacity-30 rounded-lg text-black transition-colors"
                                                >
                                                    {showIndividualRooms ? 'Hide Individual Rooms' : 'See Individual Rooms'}
                                                </button>
                                            </div>
                                        </div>
                                        
                                        {/* Individual Room Availability - Conditionally shown */}
                                        {showIndividualRooms && (
                                            <>
                                                {/* Separator */}
                                                <div className="my-6 border-t border-white border-opacity-20"></div>
                                                
                                                {/* Individual Room Availability */}
                                                <div>
                                                    <h3 className="text-lg font-bold mb-4 text-black font-royal">Individual Room Details</h3>
                                                    <div className="space-y-0.5">
                                                        {Object.entries(availabilityData).map(([roomId, roomSlots]) => (
                                                            <div key={roomId} className="bg-white bg-opacity-10 rounded-lg p-3">
                                                                {/* Room header with room name */}
                                                                <div className="mb-2">
                                                                    <h4 className="text-sm font-bold text-black">Study Room {roomId}</h4>
                                                                </div>
                                                                
                                                                {/* Single row layout matching the top section */}
                                                                <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${roomSlots.length}, minmax(0, 1fr))` }}>
                                                                    {roomSlots.map((slot, index) => (
                                                                        <button
                                                                            key={index}
                                                                            onClick={() => handleSlotClick(index, slot.displayTime)}
                                                                            disabled={!slot.available}
                                                                            className={`p-1 sm:p-2 rounded text-xs font-medium transition-colors min-h-[28px] sm:min-h-[36px] w-full touch-manipulation ${
                                                                                slot.available
                                                                                    ? selectedSlot && selectedSlot.roomId === roomId && isSlotSelected(index)
                                                                                        ? 'bg-blue-500 text-white border-2 border-blue-700'
                                                                                        : 'bg-green-500 text-white hover:bg-green-600 cursor-pointer active:bg-green-700'
                                                                                    : 'bg-red-500 text-white cursor-not-allowed opacity-75'
                                                                            }`}
                                                                            title={`${slot.displayTime} - ${slot.available ? 'Available' : 'Occupied'}`}
                                                                        >
                                                                            <span className="block">{slot.available ? '✓' : '✗'}</span>
                                                                        </button>
                                                                    ))}
                                                                </div>
                                                                
                                                                {/* Room-specific stats */}
                                                                <div className="mt-2 flex flex-wrap gap-2 text-xs">
                                                                    <div className="flex items-center gap-1">
                                                                        <span className="text-black font-medium">Available:</span>
                                                                        <span className="text-green-700 font-bold">
                                                                            {roomSlots.filter(slot => slot.available).length}
                                                                        </span>
                                                                    </div>
                                                                    <div className="flex items-center gap-1">
                                                                        <span className="text-black font-medium">Occupied:</span>
                                                                        <span className="text-red-700 font-bold">
                                                                            {roomSlots.filter(slot => !slot.available).length}
                                                                        </span>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            </>
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
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-6">
                            <div>
                                <h2 className="text-xl sm:text-2xl font-bold text-white font-royal">My Bookings</h2>
                            </div>

                        </div>
                        
                        {isLoadingBookings ? (
                            <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-8 border-2 border-black border-opacity-90">
                                <div className="flex items-center justify-center space-x-3">
                                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-black"></div>
                                    <span className="text-black">Loading your bookings...</span>
                                </div>
                            </div>
                        ) : getAllBookings().length > 0 ? (
                            <div className="space-y-4">
                                {/* Status Filter Tabs */}
                                {(() => {
                                    const allBookings = getAllBookings();
                                    const confirmedCount = allBookings.filter(b => b.status === 'confirmed').length;
                                    const pendingCount = allBookings.filter(b => b.status === 'pending').length;
                                    const cancelledCount = allBookings.filter(b => b.status === 'cancelled').length;
                                    
                                    return (
                                        <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-4 border-2 border-black border-opacity-90">
                                            <div className="grid grid-cols-3 gap-2 sm:gap-4">
                                                <div className="text-center p-3 bg-white bg-opacity-20 rounded-lg border-2 border-black border-opacity-90">
                                                    <div className="text-lg sm:text-xl font-black text-black font-royal">{confirmedCount}</div>
                                                    <div className="text-xs sm:text-sm text-black font-bold">Confirmed</div>
                                                </div>
                                                <div className="text-center p-3 bg-white bg-opacity-20 rounded-lg border-2 border-black border-opacity-90">
                                                    <div className="text-lg sm:text-xl font-black text-black font-royal">{pendingCount}</div>
                                                    <div className="text-xs sm:text-sm text-black font-bold">Monitoring</div>
                                                </div>
                                                <div className="text-center p-3 bg-white bg-opacity-20 rounded-lg border-2 border-black border-opacity-90">
                                                    <div className="text-lg sm:text-xl font-black text-black font-royal">{cancelledCount}</div>
                                                    <div className="text-xs sm:text-sm text-black font-bold">Cancelled</div>
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })()}
                                
                                {/* Bookings List */}
                                <div className="space-y-4">
                                    {getAllBookings().map((booking) => (
                                        <div
                                            key={booking.id}
                                            className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl border-2 border-black border-opacity-90 overflow-hidden transition-all hover:bg-opacity-15"
                                        >
                                            {/* Status Header */}
                                            <div className={`px-4 py-3 border-b-2 border-black border-opacity-90 ${
                                                booking.status === 'confirmed' ? 'bg-green-100 bg-opacity-60' :
                                                booking.status === 'pending' ? 'bg-blue-100 bg-opacity-60' : 
                                                'bg-gray-100 bg-opacity-60'
                                            }`}>
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center space-x-2">
                                                        <span className="text-black font-bold text-sm sm:text-base font-royal">
                                                            {booking.status === 'confirmed' ? 'Booking Confirmed' : 
                                                             booking.status === 'pending' ? 'Actively Monitoring' : 
                                                             'Request Cancelled'}
                                                        </span>
                                                    </div>
                                                    {booking.status === 'pending' && (
                                                        <div className="flex items-center space-x-1 text-black text-xs font-medium">
                                                            <div className="animate-pulse w-2 h-2 bg-blue-600 rounded-full"></div>
                                                            <span>Live</span>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                            
                                            {/* Main Content */}
                                            <div className="p-4 sm:p-6">
                                                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                                                    {/* Booking Details */}
                                                    <div className="lg:col-span-2 space-y-3">
                                                        <div>
                                                            <h3 className="text-lg sm:text-xl font-bold text-black font-royal mb-1">
                                                                {booking.roomName}
                                                            </h3>                                            {booking.status === 'pending' && (
                                                <p className="text-sm text-gray-700">Watching for availability</p>
                                            )}
                                                        </div>
                                                                         <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                            <div>
                                                <div className="text-sm text-gray-700 mb-1">Date</div>
                                                <div className="font-medium text-black">
                                                    {(() => {
                                                        const date = new Date(booking.date);
                                                        return date.toLocaleDateString('en-US', {
                                                            weekday: 'long',
                                                            year: 'numeric',
                                                            month: 'long',
                                                            day: 'numeric'
                                                        });
                                                    })()}
                                                </div>
                                            </div>
                                            
                                            <div>
                                                <div className="text-sm text-gray-700 mb-1">Time</div>
                                                <div className="font-medium text-black">{booking.time}</div>
                                            </div>
                                            
                                            <div className="sm:col-span-2">
                                                <div className="text-sm text-gray-700 mb-1">Duration</div>
                                                <div className="font-medium text-black">{booking.duration}</div>
                                            </div>
                                        </div>
                                                                         {/* Additional Info */}
                                        {booking.monitoringRequest?.success_details?.booking_id && (
                                            <div className="bg-green-50 bg-opacity-80 border-2 border-green-200 border-opacity-90 rounded-lg p-3">
                                                <div className="flex items-center space-x-2">
                                                    <div>
                                                        <div className="text-sm text-green-800 font-medium">Booking Confirmation</div>
                                                        <div className="text-sm text-green-900 font-bold">ID: {booking.monitoringRequest.success_details.booking_id}</div>
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                        
                                        {booking.monitoringRequest?.error_message && (
                                            <div className="bg-red-50 bg-opacity-80 border-2 border-red-200 border-opacity-90 rounded-lg p-3">
                                                <div className="flex items-center space-x-2">
                                                    <div>
                                                        <div className="text-sm text-red-800 font-medium">Error Details</div>
                                                        <div className="text-sm text-red-900 font-bold">{booking.monitoringRequest.error_message}</div>
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                                    </div>
                                                    
                                                    {/* Actions */}
                                                    <div className="flex flex-col justify-center space-y-2">
                                                        {booking.status === 'pending' && (
                                                            <button 
                                                                onClick={() => stopMonitoringRequest(booking.id)}
                                                                className="w-full py-3 px-4 rounded-lg font-semibold text-sm bg-red-500 hover:bg-red-600 transition-colors text-white border-2 border-black flex items-center justify-center space-x-2"
                                                            >
                                                                <span>Stop Monitoring</span>
                                                            </button>
                                                        )}
                                                        
                                                        {booking.status === 'confirmed' && (
                                                            <>
                                                                <button className="w-full py-3 px-4 rounded-lg font-semibold text-sm bg-blue-400 hover:bg-blue-500 transition-colors text-white border-2 border-black flex items-center justify-center space-x-2">
                                                                    <span>View Details</span>
                                                                </button>
                                                                <button className="w-full py-2 px-4 rounded-lg font-medium text-sm bg-white bg-opacity-20 hover:bg-opacity-30 transition-colors text-black border-2 border-black border-opacity-90 flex items-center justify-center space-x-2">
                                                                    <span>Email Reminder</span>
                                                                </button>
                                                            </>
                                                        )}
                                                        
                                                        {booking.status === 'cancelled' && (
                                                            <button className="w-full py-3 px-4 rounded-lg font-semibold text-sm bg-gray-500 text-white cursor-not-allowed opacity-75 flex items-center justify-center space-x-2 border-2 border-black">
                                                                <span>Request Ended</span>
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <div className="text-center py-12">
                                <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-xl p-8 border-2 border-black border-opacity-90">
                                    <div className="mb-4">
                                        <div className="w-20 h-20 mx-auto mb-4 bg-white bg-opacity-20 rounded-full flex items-center justify-center">
                                            <span className="text-3xl font-bold text-black">B</span>
                                        </div>
                                        <h3 className="text-xl font-bold text-black mb-2 font-royal">No Bookings Yet</h3>
                                        <p className="text-gray-700 text-base mb-6">
                                            You haven't made any bookings or monitoring requests yet.
                                        </p>
                                        <div className="space-y-2 text-sm text-gray-600">
                                            <p><strong>Tip:</strong> Use the booking form above to reserve a time slot</p>
                                            <p><strong>Smart Monitoring:</strong> We'll automatically book when slots become available</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}

export default Dashboard