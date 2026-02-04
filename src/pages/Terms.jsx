import { Link } from 'react-router-dom';

function Terms() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="bg-white rounded-lg shadow-md p-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-8">Terms of Use</h1>
          
          <div className="prose prose-lg max-w-none text-gray-700">
            <p className="text-sm text-gray-500 mb-6">Last updated: {new Date().toLocaleDateString()}</p>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Acceptance of Terms</h2>
              <p className="mb-4">
                By accessing and using RabbitMiles, you agree to be bound by these Terms of Use. 
                If you do not agree to these terms, please do not use our service.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Description of Service</h2>
              <p className="mb-4">
                RabbitMiles is a free service that connects to your Strava account to track and analyze your 
                activities on the Swamp Rabbit Trail. We provide personal statistics, projections, and optional 
                leaderboards for the local running community.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Beta Status</h2>
              <p className="mb-4">
                RabbitMiles is currently in beta. The service is provided &quot;as is&quot; without warranties. 
                Features may change, and the service may experience downtime or interruptions.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">User Responsibilities</h2>
              <p className="mb-4">When using RabbitMiles, you agree to:</p>
              <ul className="list-disc pl-6 mb-4 space-y-2">
                <li>Provide accurate information when connecting your Strava account</li>
                <li>Use the service in compliance with all applicable laws and regulations</li>
                <li>Not attempt to reverse engineer, hack, or abuse the service</li>
                <li>Respect other users&apos; privacy and data</li>
                <li>Not use automated tools to scrape or collect data from the service</li>
              </ul>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Strava Integration</h2>
              <p className="mb-4">
                RabbitMiles uses Strava&apos;s API and OAuth to access your activity data. By connecting your account, 
                you also agree to comply with{' '}
                <a 
                  href="https://www.strava.com/legal/terms" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-orange-600 hover:text-orange-700 underline"
                >
                  Strava&apos;s Terms of Service
                </a>. 
                RabbitMiles is not affiliated with or endorsed by Strava, Inc.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Data Accuracy</h2>
              <p className="mb-4">
                We make reasonable efforts to accurately calculate your trail miles based on GPS data. However, 
                GPS accuracy varies, and we use a tolerance buffer to determine if activities are on the trail. 
                Some activities may not count if they are outside this buffer, and we cannot guarantee 100% accuracy.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Leaderboards</h2>
              <p className="mb-4">
                Participation in leaderboards is optional. By opting in, you agree to share your chosen display name 
                and trail totals with other users. You can opt out at any time from the Settings page.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Intellectual Property</h2>
              <p className="mb-4">
                RabbitMiles and its original content, features, and functionality are owned by the service operators 
                and are protected by copyright and other intellectual property laws.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Limitation of Liability</h2>
              <p className="mb-4">
                RabbitMiles is provided free of charge on an &quot;as is&quot; basis. We are not liable for any damages, 
                data loss, or service interruptions. Use the service at your own risk.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Account Termination</h2>
              <p className="mb-4">
                We reserve the right to suspend or terminate accounts that violate these terms or engage in abusive behavior. 
                You may disconnect your account at any time from the Settings page.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Changes to Terms</h2>
              <p className="mb-4">
                We may update these Terms of Use from time to time. Continued use of the service after changes 
                constitutes acceptance of the new terms.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Governing Law</h2>
              <p className="mb-4">
                These terms are governed by the laws of the United States and the state where the service is operated.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Contact</h2>
              <p className="mb-4">
                If you have questions about these Terms of Use, please reach out via{' '}
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

export default Terms;
