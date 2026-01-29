import { useState } from 'react';
import { Link } from 'react-router-dom';

const BACKEND_BASE_URL = import.meta.env.VITE_BACKEND_BASE_URL;

function ConnectStrava() {
  const [isConnecting, setIsConnecting] = useState(false);
  const [openFaqIndex, setOpenFaqIndex] = useState(null);

  const handleConnectStrava = () => {
    setIsConnecting(true);
    
    // Redirect to backend OAuth endpoint
    // The backend will handle the OAuth flow and redirect to Strava
    const oauthUrl = `${BACKEND_BASE_URL}/auth/strava`;
    window.location.href = oauthUrl;
  };

  const handleLearnMore = () => {
    document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' });
  };

  const toggleFaq = (id) => {
    setOpenFaqIndex(openFaqIndex === id ? null : id);
  };

  const howItWorksSteps = [
    {
      id: "sign-in",
      icon: (
        <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1"></path>
        </svg>
      ),
      title: "Sign in with Strava",
      description: "We never store your Strava password."
    },
    {
      id: "fetch-activities",
      icon: (
        <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"></path>
        </svg>
      ),
      title: "We fetch your recent activities",
      description: "We analyze the GPS track against the Swamp Rabbit Trail."
    },
    {
      id: "see-miles",
      icon: (
        <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
        </svg>
      ),
      title: "See your miles and time on the trail",
      description: "Personal totals, projections, and optional leaderboards."
    }
  ];

  const features = [
    { id: "personal-totals", icon: "📊", title: "Personal totals", description: "Last week, month, year" },
    { id: "time-on-trail", icon: "⏱️", title: "Time on trail", description: "Elapsed time, moving time toggle" },
    { id: "projections", icon: "📈", title: "Projections", description: "On pace for this week, month, year" },
    { id: "leaderboards", icon: "🏆", title: "Opt-in leaderboards", description: "Only shared if you join" },
    { id: "data-control", icon: "🔒", title: "Data control", description: "Revoke access and delete your data anytime" }
  ];

  const faqs = [
    {
      id: "strava-access",
      question: "What do you access on my Strava account?",
      answer: "We request read access to your activities. This allows us to fetch your GPS tracks and analyze them against the Swamp Rabbit Trail. We use secure OAuth tokens and never store your Strava password."
    },
    {
      id: "share-activities",
      question: "Will you share my activities?",
      answer: "No, not unless you opt in to leaderboards. Your activity data remains private by default. If you join a leaderboard, only your totals and chosen display name are visible to others."
    },
    {
      id: "disconnect-delete",
      question: "How do I disconnect or delete my data?",
      answer: "Go to the Settings page and click 'Disconnect Strava'. Your data will be deleted from our system within 30 days of disconnection."
    },
    {
      id: "miles-not-count",
      question: "Why do some miles not count?",
      answer: "We use GPS tolerance and a buffer to determine if an activity is on the Swamp Rabbit Trail. Activities must be within a certain distance of the trail to count."
    },
    {
      id: "is-free",
      question: "Is this free?",
      answer: "Yes! RabbitMiles is currently free during beta. We're building this for the local running community."
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-white to-gray-50">
      {/* Hero Section - Above the Fold */}
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 pt-12 pb-16">
        <div className="text-center">
          {/* Headline */}
          <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold text-gray-900 mb-6">
            Track your Swamp Rabbit Trail miles
          </h1>
          
          {/* Subhead */}
          <p className="text-xl sm:text-2xl text-gray-600 mb-10 max-w-3xl mx-auto">
            Connect Strava to compute miles and hours you spent on the trail. Opt in to share totals with friends.
          </p>

          {/* CTAs */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-8">
            {/* Primary CTA */}
            <button
              onClick={handleConnectStrava}
              disabled={isConnecting}
              className="inline-flex items-center justify-center px-8 py-4 border border-transparent text-lg font-semibold rounded-lg text-white bg-orange-600 hover:bg-orange-700 focus:outline-none focus:ring-4 focus:ring-orange-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-lg hover:shadow-xl"
              aria-label="Connect your Strava account to start tracking"
            >
              {isConnecting ? (
                <>
                  <svg className="animate-spin -ml-1 mr-3 h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Connecting...
                </>
              ) : (
                <>
                  <svg className="w-6 h-6 mr-2" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066m-7.008-5.599l2.836 5.598h4.172L10.463 0l-7 13.828h4.169"></path>
                  </svg>
                  Connect with Strava
                </>
              )}
            </button>

            {/* Secondary CTA */}
            <button
              onClick={handleLearnMore}
              className="inline-flex items-center justify-center px-8 py-4 border-2 border-gray-300 text-lg font-semibold rounded-lg text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-4 focus:ring-gray-300 focus:ring-offset-2 transition-colors"
              aria-label="Learn how RabbitMiles works"
            >
              Learn how it works
            </button>
          </div>

          {/* Trust Signals */}
          <div className="space-y-3 text-sm text-gray-600 max-w-2xl mx-auto">
            <p>
              We do not sell your data. See our{' '}
              <Link to="/privacy" className="text-orange-600 hover:text-orange-700 underline focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-1 rounded">
                Privacy Policy
              </Link>
              .
            </p>
            <div className="flex flex-wrap justify-center gap-4 text-xs text-gray-500">
              <span className="inline-flex items-center px-3 py-1 rounded-full bg-blue-50 text-blue-700">
                🤝 Built for friends
              </span>
              <span className="inline-flex items-center px-3 py-1 rounded-full bg-green-50 text-green-700">
                🏆 Opt-in leaderboards only
              </span>
            </div>
            
            {/* Strava Attribution */}
            <div className="pt-4 flex items-center justify-center gap-2 text-xs text-gray-400">
              <span>Powered by</span>
              <svg className="w-16 h-4" fill="currentColor" viewBox="0 0 432 100" aria-label="Strava">
                <path d="M94.5 55.5L74.1 5h-20l20.4 50.5h20zm26.6 0L141.5 5h-20L101.1 55.5h20zM53.7 55.5L34.1 5h-20L34.5 55.5h19.2zm187.5-7.9c0-16.1-9.7-22.5-23.4-22.5-14.6 0-25.5 9.7-25.5 25.5 0 16.1 9.7 25.5 25.5 25.5 13.6 0 22.4-7.1 23.3-20.3h-10.7c-.8 6.8-5.6 11-12.6 11-8.4 0-14.1-6.1-14.1-16.2 0-9.4 5.6-16.2 14.1-16.2 6.6 0 11.3 3.6 12.6 10.2h10.8v3zm58.5 8c0-15.8-9.7-25.5-25.5-25.5s-25.5 9.7-25.5 25.5 9.7 25.5 25.5 25.5 25.5-9.7 25.5-25.5zm-10.7 0c0 10.1-5.6 16.2-14.8 16.2s-14.8-6.1-14.8-16.2 5.6-16.2 14.8-16.2 14.8 6.1 14.8 16.2zm58.5 20.4V56.3c0-10.7-6.3-16.1-16.1-16.1-8 0-14.8 4.7-16.1 12.6h10.1c.8-3.6 3.6-5.6 7.4-5.6 4.7 0 7.4 2.8 7.4 7.4v3.6l-12.6.8c-11 .8-18.4 5.6-18.4 15 0 9.4 7.4 15 17.8 15 7.9 0 13.6-3.6 16.1-9.4h.3v8.4h10.1v-12zm-10.7-13.6c0 7.9-5.6 13.6-14.1 13.6-5.6 0-9.4-2.8-9.4-7.4 0-4.7 3.6-7.4 9.4-7.9l14.1-.8v2.5zm66.9-22c-1.3-7.9-8-12.6-18.4-12.6-11.3 0-18.4 5.6-18.4 13.6 0 6.8 4.7 11 13.6 12.6l8.4 1.3c5.6.8 8 2.8 8 6.1 0 3.6-3.9 6.1-10.1 6.1-6.1 0-10.1-2.5-11-7.9h-10.7c1.3 9.4 8.4 15 21.7 15 12.6 0 20.8-6.1 20.8-14.1 0-6.8-4.7-10.7-13.6-12.6l-8.4-1.3c-6.1-.8-8.4-2.8-8.4-5.6 0-3.6 3.6-6.1 9.4-6.1 5.6 0 9.4 2.8 10.1 7.4h10zM189.5 5h-10.7v50.5h10.7V5zm-62.2 50.5h10.7V31.4h16.1v-9.4h-16.1V5h-10.7v50.5z"></path>
              </svg>
            </div>
          </div>
        </div>
      </div>

      {/* How it Works Section */}
      <div id="how-it-works" className="bg-white py-16">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-gray-900 text-center mb-12">
            How it works
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {howItWorksSteps.map((step) => (
              <div key={step.id} className="text-center">
                <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-orange-100 text-orange-600 mb-4">
                  {step.icon}
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">
                  {step.title}
                </h3>
                <p className="text-gray-600">
                  {step.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Key Features Section */}
      <div className="bg-gray-50 py-16">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-gray-900 text-center mb-12">
            Key features
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature) => (
              <div key={feature.id} className="bg-white rounded-lg shadow-sm p-6 hover:shadow-md transition-shadow">
                <div className="text-3xl mb-3">{feature.icon}</div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  {feature.title}
                </h3>
                <p className="text-gray-600 text-sm">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Example Visuals Section */}
      <div className="bg-white py-16">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-gray-900 text-center mb-8">
            See your progress at a glance
          </h2>
          <div className="bg-gradient-to-br from-orange-50 to-blue-50 rounded-xl p-8 text-center">
            <div className="max-w-2xl mx-auto">
              <p className="text-gray-600 mb-6">
                Track your totals, view projections, and see how you compare with friends on the trail.
              </p>
              <div className="bg-white rounded-lg shadow-lg p-6 text-left">
                <div className="grid grid-cols-3 gap-4 mb-4">
                  <div className="bg-gray-50 rounded p-3">
                    <div className="text-xs text-gray-500 mb-1">This Week</div>
                    <div className="text-2xl font-bold text-gray-900">12.4 mi</div>
                  </div>
                  <div className="bg-gray-50 rounded p-3">
                    <div className="text-xs text-gray-500 mb-1">This Month</div>
                    <div className="text-2xl font-bold text-gray-900">45.2 mi</div>
                  </div>
                  <div className="bg-gray-50 rounded p-3">
                    <div className="text-xs text-gray-500 mb-1">This Year</div>
                    <div className="text-2xl font-bold text-gray-900">156.8 mi</div>
                  </div>
                </div>
                <div className="bg-orange-50 rounded p-3 border-l-4 border-orange-500">
                  <div className="text-xs text-orange-700 mb-1">Projection</div>
                  <div className="text-sm text-gray-900">On pace for <span className="font-bold">600 miles</span> this year!</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* FAQ Section */}
      <div className="bg-gray-50 py-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-gray-900 text-center mb-12">
            Frequently asked questions
          </h2>
          <div className="space-y-4">
            {faqs.map((faq) => (
              <div key={faq.id} className="bg-white rounded-lg shadow-sm overflow-hidden">
                <button
                  onClick={() => toggleFaq(faq.id)}
                  className="w-full px-6 py-4 text-left flex justify-between items-center hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-orange-500"
                  aria-expanded={openFaqIndex === faq.id}
                  aria-controls={`faq-answer-${faq.id}`}
                >
                  <span className="font-semibold text-gray-900">{faq.question}</span>
                  <svg
                    className={`w-5 h-5 text-gray-500 transform transition-transform ${
                      openFaqIndex === faq.id ? 'rotate-180' : ''
                    }`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path>
                  </svg>
                </button>
                {openFaqIndex === faq.id && (
                  <div id={`faq-answer-${faq.id}`} className="px-6 pb-4 text-gray-600">
                    {faq.answer}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Leaderboard Preview Section */}
      <div className="bg-white py-16">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-gradient-to-br from-purple-50 to-pink-50 rounded-xl p-8 text-center">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">
              Join the leaderboard
            </h2>
            <p className="text-gray-700 mb-6 max-w-2xl mx-auto">
              Leaderboards are opt-in. You choose your display name and what to share. 
              Compare your totals with friends and the local running community.
            </p>
            <button
              disabled
              className="inline-flex items-center px-8 py-4 border-2 border-gray-300 text-lg font-semibold rounded-lg text-gray-400 bg-gray-100 cursor-not-allowed"
              aria-label="Join leaderboard (available after connecting Strava)"
            >
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path>
              </svg>
              Join leaderboard
            </button>
            <p className="text-xs text-gray-500 mt-3">
              Connect your Strava account first to join leaderboards
            </p>
          </div>
        </div>
      </div>

      {/* Footer */}
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
                    href="mailto:support@rabbitmiles.com" 
                    className="hover:text-white focus:outline-none focus:underline"
                  >
                    support@rabbitmiles.com
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
    </div>
  );
}

export default ConnectStrava;
