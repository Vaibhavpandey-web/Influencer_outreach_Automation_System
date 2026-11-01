import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import apify_scraper as scraper
import pipeline


class WorkflowTests(unittest.TestCase):
    def test_engagement_needs_three_valid_posts(self):
        self.assertIsNone(scraper.calculate_engagement([{'likesCount': 10}] * 2, 1000))
        self.assertEqual(scraper.calculate_engagement([{'likesCount': 20, 'commentsCount': 5}] * 3, 1000), .025)

    def test_resume_and_fresh_collection(self):
        with tempfile.TemporaryDirectory() as directory:
            output = str(Path(directory) / 'raw.csv')
            old = scraper.build_row({'username': 'old', 'followersCount': 6000}, {}, ['skincare'])
            pd.DataFrame([old]).to_csv(output, index=False)
            with patch.object(scraper, 'APIFY_API_TOKEN', 'test'), patch.object(scraper, 'ApifyClient'), patch.object(scraper, 'run_actor') as actor:
                resumed = scraper.fetch_real_influencers(output_csv=output, target_in_range=1)
                self.assertEqual(resumed['Social Handle'].tolist(), ['@old'])
                actor.assert_not_called()
                actor.side_effect = [[{'ownerUsername': 'new', 'likesCount': 40}], [{'username': 'new', 'followersCount': 7000}]]
                fresh = scraper.fetch_real_influencers(hashtags=('skincare',), output_csv=output, target_in_range=1, fresh=True)
                self.assertEqual(fresh['Social Handle'].tolist(), ['@new'])
                self.assertEqual(pd.read_csv(output)['Social Handle'].tolist(), ['@new'])

    def test_simulation_never_connects_to_smtp(self):
        row = {'Influencer Name': 'Example', 'Contact Email': 'creator@example.com', 'Profile URL': 'https://example.com/creator', 'Filter Status': 'Passed', 'Generated Email Pitch': 'Example draft', 'Generated Instagram DM': 'Example DM', 'Email Subject': 'Example'}
        with tempfile.TemporaryDirectory() as directory, patch.object(pipeline.smtplib, 'SMTP') as smtp:
            result = pipeline.execute_sending_layer(pd.DataFrame([row]), str(Path(directory) / 'tracker.csv'))
            smtp.assert_not_called()
            self.assertEqual(result.iloc[0]['Status'], 'Simulated (not delivered)')
            self.assertEqual(result.iloc[0]['Sent'], 'No')


if __name__ == '__main__':
    unittest.main()
