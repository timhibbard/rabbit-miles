import { Link } from 'react-router-dom';

function Footer() {
  return (
    <footer className="bg-gray-900 text-gray-300 py-12">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
          <div>
            <h3 className="text-white font-semibold mb-4">RabbitMiles</h3>
            <p className="text-sm text-gray-400">
              Track your Swamp Rabbit Trail miles with Strava integration.
            </p>
          </div>
          <div>
            <h4 className="text-white font-semibold mb-4">Legal</h4>
            <ul className="space-y-2 text-sm">
              <li>
                <Link to="/privacy" className="hover:text-white focus:outline-none focus:underline">
                  Privacy Policy
                </Link>
              </li>
              <li>
                <Link to="/terms" className="hover:text-white focus:outline-none focus:underline">
                  Terms of Use
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="text-white font-semibold mb-4">Contact</h4>
            <ul className="space-y-2 text-sm">
              <li>
                <a 
                  href="https://www.strava.com/athletes/3519964" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="hover:text-white focus:outline-none focus:underline"
                >
                  Strava Profile
                </a>
              </li>
              <li>
                <a 
                  href="https://github.com/timhibbard/rabbit-miles" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="hover:text-white focus:outline-none focus:underline"
                >
                  Source Code
                </a>
              </li>
            </ul>
          </div>
        </div>
        <div className="border-t border-gray-800 pt-8 text-sm text-gray-400 text-center">
          <p>RabbitMiles is not affiliated with Strava, Inc.</p>
          <p className="mt-2">© {new Date().getFullYear()} RabbitMiles. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
}

export default Footer;
