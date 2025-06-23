import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';

interface LoginFormProps {
  onSwitchToRegister: () => void;
  onClose: () => void;
}

const LoginForm = ({ onSwitchToRegister, onClose }: LoginFormProps) => {
  const { login } = useAuth();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
    setError('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const result = await login(formData.email, formData.password);
      if (result.success) {
        onClose();
      } else {
        setError(result.message);
      }
    } catch (error) {
      setError('An unexpected error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full">
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl">
          <p className="text-red-800 text-sm">{error}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2 font-royal">
            email or username
          </label>
          <input
            type="text"
            id="email"
            name="email"
            value={formData.email}
            onChange={handleChange}
            required
            className="w-full px-4 py-3 border border-gray-300 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-[#1B38E2] focus:border-[#1B38E2] transition-colors font-royal"
            placeholder="enter your email or username"
          />
        </div>

        <div>
          <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2 font-royal">
            password
          </label>
          <input
            type="password"
            id="password"
            name="password"
            value={formData.password}
            onChange={handleChange}
            required
            className="w-full px-4 py-3 border border-gray-300 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-[#1B38E2] focus:border-[#1B38E2] transition-colors font-royal"
            placeholder="enter your password"
          />
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="w-full bg-[#1B38E2] text-white py-3 px-4 rounded-xl hover:bg-[#1530c7] focus:outline-none focus:ring-2 focus:ring-[#1B38E2] focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium font-royal"
        >
          {isLoading ? 'signing in...' : 'sign in'}
        </button>
      </form>

      <div className="mt-8 text-center">
        <p className="text-sm text-gray-600 font-royal">
          don't have an account?{' '}
          <button
            onClick={onSwitchToRegister}
            className="text-[#1B38E2] hover:text-[#1530c7] font-medium transition-colors font-royal"
          >
            sign up
          </button>
        </p>
      </div>
    </div>
  );
};

export default LoginForm;
