import { Link } from 'react-router-dom';

function Privacy() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="bg-white rounded-lg shadow-md p-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-8">Privacy Policy</h1>
          
          <div className="prose prose-lg max-w-none text-gray-700">
            <p className="text-sm text-gray-500 mb-6">Last updated: {new Date().toLocaleDateString()}</p>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Our Commitment to Your Privacy</h2>
              <p className="mb-4">
                At RabbitMiles, we respect your privacy and are committed to protecting your personal data. 
                This privacy policy explains how we collect, use, and safeguard your information when you use our service.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">What Data We Collect</h2>
              <p className="mb-4">When you connect your Strava account to RabbitMiles, we collect:</p>
              <ul className="list-disc pl-6 mb-4 space-y-2">
                <li>Your Strava profile information (name, profile picture)</li>
                <li>Your activity data (GPS tracks, distance, time, date)</li>
                <li>OAuth access tokens to securely access your Strava data</li>
              </ul>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">How We Use Your Data</h2>
              <p className="mb-4">We use your data exclusively to:</p>
              <ul className="list-disc pl-6 mb-4 space-y-2">
                <li>Analyze your activities against the Swamp Rabbit Trail GPS coordinates</li>
                <li>Calculate your personal totals and projections</li>
                <li>Display your statistics on your personal dashboard</li>
                <li>Show your totals on leaderboards (only if you opt in)</li>
              </ul>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Data Sharing</h2>
              <p className="mb-4">
                <strong>We do not sell your data.</strong> Your activity details remain private by default.
              </p>
              <p className="mb-4">
                If you opt in to leaderboards, only your chosen display name and trail totals are visible to other users. 
                Your detailed activity information, GPS tracks, and other personal data remain private.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Data Storage and Security</h2>
              <p className="mb-4">
                We store your data securely using industry-standard encryption. OAuth tokens are encrypted at rest, 
                and we never store your Strava password.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Your Rights and Control</h2>
              <p className="mb-4">You have full control over your data:</p>
              <ul className="list-disc pl-6 mb-4 space-y-2">
                <li><strong>Disconnect:</strong> You can disconnect your Strava account at any time from the Settings page</li>
                <li><strong>Delete:</strong> When you disconnect, your data is deleted from our system within 30 days</li>
                <li><strong>Opt-out:</strong> You can leave leaderboards at any time without disconnecting</li>
                <li><strong>Access:</strong> Contact us to request a copy of your stored data</li>
              </ul>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Third-Party Services</h2>
              <p className="mb-4">
                RabbitMiles uses Strava&apos;s API to access your activity data. When you connect your account, 
                you agree to Strava&apos;s terms and privacy policy as well. We recommend reviewing{' '}
                <a 
                  href="https://www.strava.com/legal/privacy" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-orange-600 hover:text-orange-700 underline"
                >
                  Strava&apos;s Privacy Policy
                </a>.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Cookies and Tracking</h2>
              <p className="mb-4">
                We use minimal cookies for essential functionality (maintaining your session). 
                We do not use third-party tracking or advertising cookies.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Changes to This Policy</h2>
              <p className="mb-4">
                We may update this privacy policy from time to time. We will notify you of any significant changes 
                by posting the new policy on this page and updating the &quot;Last updated&quot; date.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Contact Us</h2>
              <p className="mb-4">
                If you have questions about this privacy policy or your data, please reach out via{' '}
                <a 
                  href="https://www.strava.com/athletes/3519964" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-orange-600 hover:text-orange-700 underline"
                >
                  Strava
                </a>.
              </p>
            </section>
          </div>

          <div className="mt-8 pt-6 border-t border-gray-200">
            <Link 
              to="/connect" 
              className="text-orange-600 hover:text-orange-700 font-medium inline-flex items-center focus:outline-none focus:underline"
            >
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path>
              </svg>
              Back to Home
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Privacy;
