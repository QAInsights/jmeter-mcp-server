"""
Tests for the insights generator.
"""

import unittest

from analyzer.insights.generator import InsightsGenerator
from analyzer.models import Bottleneck, Recommendation


class TestInsightsGenerator(unittest.TestCase):
    """Tests for the InsightsGenerator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.generator = InsightsGenerator()
        
        # Create bottlenecks
        self.bottlenecks = [
            Bottleneck(
                endpoint="Slow Endpoint",
                metric_type="response_time",
                value=500.0,
                threshold=200.0,
                severity="high"
            ),
            Bottleneck(
                endpoint="Medium Endpoint",
                metric_type="response_time",
                value=300.0,
                threshold=200.0,
                severity="medium"
            ),
            Bottleneck(
                endpoint="Error Endpoint",
                metric_type="error_rate",
                value=15.0,
                threshold=5.0,
                severity="high"
            )
        ]
        
        # Create error analysis
        self.error_analysis = {
            "error_types": {
                "Connection timeout": 10,
                "500 Internal Server Error": 5,
                "404 Not Found": 3
            },
            "error_patterns": [
                {
                    "type": "spike",
                    "timestamp": "2023-01-01T12:00:00",
                    "error_count": 8
                }
            ]
        }
        
        # Create concurrency analysis
        self.concurrency_analysis = {
            "correlation": 0.85,
            "degradation_threshold": 50,
            "has_degradation": True
        }
    
    def test_generate_bottleneck_recommendations(self):
        """Test generating recommendations for bottlenecks."""
        recommendations = self.generator.generate_bottleneck_recommendations(self.bottlenecks)
        
        # We should have at least 2 recommendations (one for response time, one for error rate)
        self.assertGreaterEqual(len(recommendations), 2)
        
        # Check that we have recommendations for both types of bottlenecks
        recommendation_issues = [r.issue for r in recommendations]
        self.assertTrue(any("response time" in issue.lower() for issue in recommendation_issues))
        self.assertTrue(any("error rate" in issue.lower() for issue in recommendation_issues))
        
        # Check that recommendations have all required fields
        for recommendation in recommendations:
            self.assertIsNotNone(recommendation.issue)
            self.assertIsNotNone(recommendation.recommendation)
            self.assertIsNotNone(recommendation.expected_impact)
            self.assertIsNotNone(recommendation.implementation_difficulty)
    
    def test_generate_error_recommendations(self):
        """Test generating recommendations for error patterns."""
        recommendations = self.generator.generate_error_recommendations(self.error_analysis)
        
        # We should have at least 3 recommendations (one for each error type)
        self.assertGreaterEqual(len(recommendations), 3)
        
        # Check that we have recommendations for the error types
        recommendation_issues = [r.issue for r in recommendations]
        self.assertTrue(any("timeout" in issue.lower() for issue in recommendation_issues))
        self.assertTrue(any("server" in issue.lower() for issue in recommendation_issues))
        
        # Check that recommendations have all required fields
        for recommendation in recommendations:
            self.assertIsNotNone(recommendation.issue)
            self.assertIsNotNone(recommendation.recommendation)
            self.assertIsNotNone(recommendation.expected_impact)
            self.assertIsNotNone(recommendation.implementation_difficulty)
    
    def test_generate_scaling_insights(self):
        """Test generating insights on scaling behavior."""
        insights = self.generator.generate_scaling_insights(self.concurrency_analysis)
        
        # We should have at least 2 insights
        self.assertGreaterEqual(len(insights), 2)
        
        # Check that we have insights about correlation and degradation
        insight_topics = [i.topic for i in insights]
        self.assertTrue(any("correlation" in topic.lower() for topic in insight_topics))
        self.assertTrue(any("degradation" in topic.lower() for topic in insight_topics))
        
        # Check that insights have all required fields
        for insight in insights:
            self.assertIsNotNone(insight.topic)
            self.assertIsNotNone(insight.description)
            self.assertIsNotNone(insight.supporting_data)
    
    def test_prioritize_recommendations(self):
        """Test prioritizing recommendations."""
        # Create some recommendations
        recommendations = [
            Recommendation(
                issue="Critical response time issues",
                recommendation="Optimize database queries",
                expected_impact="Significant reduction in response times",
                implementation_difficulty="medium"
            ),
            Recommendation(
                issue="Moderate error rates",
                recommendation="Add error handling",
                expected_impact="Reduction in error rates",
                implementation_difficulty="low"
            ),
            Recommendation(
                issue="Minor UI issues",
                recommendation="Fix UI bugs",
                expected_impact="Improved user experience",
                implementation_difficulty="high"
            )
        ]
        
        prioritized = self.generator.prioritize_recommendations(recommendations)
        
        # We should have 3 prioritized recommendations
        self.assertEqual(len(prioritized), 3)
        
        # Check that they are sorted by priority score (descending)
        self.assertGreaterEqual(prioritized[0]["priority_score"], prioritized[1]["priority_score"])
        self.assertGreaterEqual(prioritized[1]["priority_score"], prioritized[2]["priority_score"])
        
        # Check that each prioritized recommendation has the required fields
        for item in prioritized:
            self.assertIn("recommendation", item)
            self.assertIn("priority_score", item)
            self.assertIn("priority_level", item)
    
    def test_empty_inputs(self):
        """Test handling of empty inputs."""
        self.assertEqual(len(self.generator.generate_bottleneck_recommendations([])), 0)
        self.assertEqual(len(self.generator.generate_error_recommendations({})), 0)
        self.assertGreaterEqual(len(self.generator.generate_scaling_insights({})), 1)  # Should still generate at least one insight
        self.assertEqual(len(self.generator.prioritize_recommendations([])), 0)


if __name__ == '__main__':
    unittest.main()