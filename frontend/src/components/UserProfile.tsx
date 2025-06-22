import { useAuth } from '../contexts/AuthContext';

interface UserProfileProps {
  onClose: () => void;
}

const UserProfile = ({ onClose }: UserProfileProps) => {
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    onClose();
  };

  if (!user) return null;

  return (
    <div className="absolute right-0 mt-2 w-64 bg-white rounded-md shadow-lg py-1 z-50 border border-gray-200">
      <div className="px-4 py-3 border-b border-gray-200">
        <p className="text-sm font-medium text-gray-900">{user.firstName} {user.lastName}</p>
        <p className="text-sm text-gray-500">{user.email}</p>
        <p className="text-xs text-gray-400">@{user.username}</p>
      </div>
      
      <div className="py-1">
        <button
          onClick={handleLogout}
          className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
        >
          Sign out
        </button>
      </div>
    </div>
  );
};

export default UserProfile;
