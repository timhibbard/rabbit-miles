import { Link } from 'react-router-dom';

function About() {
  const originStory = {
    year: 2026,
    challenge: "great burrito challenge",
    lapNumber: "14 or 15",
    conceptCreator: {
      name: "Blake Pratt",
      stravaUrl: "https://www.strava.com/athletes/25516095"
    },
    sherpaTarget: {
      name: "Miles Bryan",
      stravaUrl: "https://www.strava.com/athletes/57681885"
    },
    instagramPost: "https://www.instagram.com/p/DTdzTCZEuzt/"
  };

  const supportInfo = {
    betaApp: {
      title: "On Pace For Beta",
      url: "https://testflight.apple.com/join/ZnYvs7We"
    },
    creator: {
      name: "Tim Hibbard",
      stravaUrl: "https://www.strava.com/athletes/3519964"
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="bg-white rounded-lg shadow-md p-8">
          <div className="mb-8">
            <h1 className="text-4xl font-bold text-gray-900 mb-4">
              About RabbitMiles
            </h1>
            <div className="h-1 w-20 bg-orange-600 rounded"></div>
          </div>
          
          <div className="prose prose-lg max-w-none text-gray-700">
            <section className="mb-10">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4 flex items-center">
                <span className="text-3xl mr-3">🌯</span>
                The Origin Story
              </h2>
              <div className="bg-orange-50 border-l-4 border-orange-600 p-6 mb-6">
                <p className="mb-4 leading-relaxed">
                  During the{' '}
                  <a 
                    href={originStory.instagramPost}
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-orange-600 hover:text-orange-700 underline font-medium"
                  >
                    {originStory.challenge} of {originStory.year}
                  </a>
                  , a group of 5-6 runners were acting as sherpa for{' '}
                  <a 
                    href={originStory.sherpaTarget.stravaUrl}
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-orange-600 hover:text-orange-700 underline font-medium"
                  >
                    {originStory.sherpaTarget.name}
                  </a>
                  {' '}through what would become a legendary run.
                </p>
                <p className="mb-4 leading-relaxed">
                  Somewhere around lap {originStory.lapNumber},{' '}
                  <a 
                    href={originStory.conceptCreator.stravaUrl}
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-orange-600 hover:text-orange-700 underline font-medium"
                  >
                    {originStory.conceptCreator.name}
                  </a>
                  {' '}voiced a thought that would change everything:
                </p>
                <blockquote className="border-l-4 border-orange-400 pl-4 italic text-gray-800 text-lg">
                  &ldquo;I wish there was an app that showed me how many miles I&apos;ve ran on the trail&rdquo;
                </blockquote>
                <p className="mt-4 leading-relaxed font-medium text-gray-900">
                  And just like that, RabbitMiles was born. 🐰
                </p>
              </div>
            </section>

            <section className="mb-10">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4 flex items-center">
                <span className="text-3xl mr-3">💡</span>
                What We Do
              </h2>
              <p className="mb-4 leading-relaxed">
                RabbitMiles connects to your Strava account and automatically tracks every mile 
                you run on the Swamp Rabbit Trail. No manual logging, no guesswork—just pure data 
                showing you exactly how much you&apos;ve conquered of this amazing trail.
              </p>
            </section>

            <section className="mb-10">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4 flex items-center">
                <span className="text-3xl mr-3">🤝</span>
                Support This Project
              </h2>
              <div className="space-y-4">
                <p className="leading-relaxed">
                  RabbitMiles is a passion project built for the running community. 
                  If you find it useful and want to support more projects like this, check out:
                </p>
                <div className="bg-gray-50 rounded-lg p-6 space-y-4">
                  <div className="flex items-start">
                    <div className="flex-shrink-0">
                      <svg className="h-6 w-6 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
                      </svg>
                    </div>
                    <div className="ml-4">
                      <h3 className="text-lg font-medium text-gray-900">
                        {supportInfo.betaApp.title}
                      </h3>
                      <p className="mt-1 text-gray-600">
                        Another running app currently in beta testing
                      </p>
                      <a 
                        href={supportInfo.betaApp.url}
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="mt-2 inline-flex items-center text-orange-600 hover:text-orange-700 font-medium"
                      >
                        Join the beta
                        <svg className="ml-1 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"></path>
                        </svg>
                      </a>
                    </div>
                  </div>
                  <div className="flex items-start">
                    <div className="flex-shrink-0">
                      <svg className="h-6 w-6 text-orange-600" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066m-7.008-5.599l2.836 5.598h4.172L10.463 0l-7 13.828h4.169"></path>
                      </svg>
                    </div>
                    <div className="ml-4">
                      <h3 className="text-lg font-medium text-gray-900">
                        Follow on Strava
                      </h3>
                      <p className="mt-1 text-gray-600">
                        Connect with the creator and stay updated
                      </p>
                      <a 
                        href={supportInfo.creator.stravaUrl}
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="mt-2 inline-flex items-center text-orange-600 hover:text-orange-700 font-medium"
                      >
                        Follow {supportInfo.creator.name}
                        <svg className="ml-1 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"></path>
                        </svg>
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4 flex items-center">
                <span className="text-3xl mr-3">🏃</span>
                Built for Runners, By Runners
              </h2>
              <p className="leading-relaxed">
                This app was born out of a real need from real runners hitting real miles. 
                We hope it helps you track your progress and maybe even motivates you to 
                put in a few more laps on the Swamp Rabbit Trail.
              </p>
            </section>
          </div>

          <div className="mt-10 pt-6 border-t border-gray-200">
            <Link 
              to="/" 
              className="text-orange-600 hover:text-orange-700 font-medium inline-flex items-center focus:outline-none focus:underline"
            >
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path>
              </svg>
              Back to Dashboard
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

export default About;
