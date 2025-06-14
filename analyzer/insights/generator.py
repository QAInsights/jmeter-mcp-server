"""
Insights generator for JMeter test results.

This module provides functionality for generating insights and recommendations
based on JMeter test results analysis, including bottleneck recommendations,
error pattern analysis, scaling insights, and recommendation prioritization.
"""

from typing import Dict, List, Optional, Tuple, Union

from analyzer.models import (Bottleneck, EndpointMetrics, Insight,
                           OverallMetrics, Recommendation, TestResults)


class InsightsGenerator:
    """Generator for insights and recommendations based on test results analysis."""
    
    def generate_bottleneck_recommendations(self, bottlenecks: List[Bottleneck]) -> List[Recommendation]:
        """Generate recommendations for addressing identified bottlenecks.
        
        Args:
            bottlenecks: List of Bottleneck objects
            
        Returns:
            List of Recommendation objects
        """
        recommendations = []
        
        # Process response time bottlenecks
        response_time_bottlenecks = [b for b in bottlenecks if b.metric_type == "response_time"]
        if response_time_bottlenecks:
            # Group by severity
            high_severity = [b for b in response_time_bottlenecks if b.severity == "high"]
            medium_severity = [b for b in response_time_bottlenecks if b.severity == "medium"]
            
            # Generate recommendations for high severity bottlenecks
            if high_severity:
                endpoints = ", ".join(b.endpoint for b in high_severity[:3])
                recommendation = Recommendation(
                    issue=f"Critical response time issues in endpoints: {endpoints}",
                    recommendation="Optimize database queries, add caching, or consider asynchronous processing for these endpoints",
                    expected_impact="Significant reduction in response times and improved user experience",
                    implementation_difficulty="medium"
                )
                recommendations.append(recommendation)
            
            # Generate recommendations for medium severity bottlenecks
            if medium_severity:
                endpoints = ", ".join(b.endpoint for b in medium_severity[:3])
                recommendation = Recommendation(
                    issue=f"Moderate response time issues in endpoints: {endpoints}",
                    recommendation="Profile the code to identify bottlenecks and optimize the most expensive operations",
                    expected_impact="Moderate improvement in response times",
                    implementation_difficulty="medium"
                )
                recommendations.append(recommendation)
        
        # Process error rate bottlenecks
        error_rate_bottlenecks = [b for b in bottlenecks if b.metric_type == "error_rate"]
        if error_rate_bottlenecks:
            # Group by severity
            high_severity = [b for b in error_rate_bottlenecks if b.severity == "high"]
            medium_severity = [b for b in error_rate_bottlenecks if b.severity == "medium"]
            
            # Generate recommendations for high severity bottlenecks
            if high_severity:
                endpoints = ", ".join(b.endpoint for b in high_severity[:3])
                recommendation = Recommendation(
                    issue=f"High error rates in endpoints: {endpoints}",
                    recommendation="Investigate error logs, add proper error handling, and fix the root causes of errors",
                    expected_impact="Significant reduction in error rates and improved reliability",
                    implementation_difficulty="high"
                )
                recommendations.append(recommendation)
            
            # Generate recommendations for medium severity bottlenecks
            if medium_severity:
                endpoints = ", ".join(b.endpoint for b in medium_severity[:3])
                recommendation = Recommendation(
                    issue=f"Moderate error rates in endpoints: {endpoints}",
                    recommendation="Review error handling and add appropriate validation and error recovery mechanisms",
                    expected_impact="Moderate reduction in error rates",
                    implementation_difficulty="medium"
                )
                recommendations.append(recommendation)
        
        return recommendations
    
    def generate_error_recommendations(self, error_analysis: Dict) -> List[Recommendation]:
        """Generate recommendations for addressing error patterns.
        
        Args:
            error_analysis: Dictionary containing error analysis results
            
        Returns:
            List of Recommendation objects
        """
        recommendations = []
        
        # Process error types
        error_types = error_analysis.get("error_types", {})
        if error_types:
            # Find the most common error types
            sorted_errors = sorted(error_types.items(), key=lambda x: x[1], reverse=True)
            top_errors = sorted_errors[:3]
            
            for error_type, count in top_errors:
                if "timeout" in error_type.lower():
                    recommendation = Recommendation(
                        issue=f"Timeout errors ({count} occurrences)",
                        recommendation="Increase timeout thresholds, optimize slow operations, or implement circuit breakers",
                        expected_impact="Reduction in timeout errors and improved reliability",
                        implementation_difficulty="medium"
                    )
                    recommendations.append(recommendation)
                
                elif "connection" in error_type.lower():
                    recommendation = Recommendation(
                        issue=f"Connection errors ({count} occurrences)",
                        recommendation="Implement connection pooling, retry mechanisms, or check network configuration",
                        expected_impact="Improved connection stability and reduced errors",
                        implementation_difficulty="medium"
                    )
                    recommendations.append(recommendation)
                
                elif "500" in error_type or "server" in error_type.lower():
                    recommendation = Recommendation(
                        issue=f"Server errors ({count} occurrences)",
                        recommendation="Check server logs, fix application bugs, and add proper error handling",
                        expected_impact="Reduction in server errors and improved reliability",
                        implementation_difficulty="high"
                    )
                    recommendations.append(recommendation)
                
                elif "400" in error_type or "client" in error_type.lower():
                    recommendation = Recommendation(
                        issue=f"Client errors ({count} occurrences)",
                        recommendation="Validate input data, fix client-side issues, and improve error messages",
                        expected_impact="Reduction in client errors and improved user experience",
                        implementation_difficulty="medium"
                    )
                    recommendations.append(recommendation)
                
                else:
                    recommendation = Recommendation(
                        issue=f"{error_type} errors ({count} occurrences)",
                        recommendation="Investigate the root cause and implement appropriate error handling",
                        expected_impact="Reduction in errors and improved reliability",
                        implementation_difficulty="medium"
                    )
                    recommendations.append(recommendation)
        
        # Process error patterns
        error_patterns = error_analysis.get("error_patterns", [])
        if error_patterns:
            for pattern in error_patterns:
                pattern_type = pattern.get("type", "")
                
                if pattern_type == "spike":
                    recommendation = Recommendation(
                        issue="Error spike detected during the test",
                        recommendation="Investigate what happened during the spike period and address the underlying cause",
                        expected_impact="Prevention of error spikes in production",
                        implementation_difficulty="medium"
                    )
                    recommendations.append(recommendation)
                
                elif pattern_type == "increasing":
                    recommendation = Recommendation(
                        issue="Increasing error rate over time",
                        recommendation="Check for resource leaks, memory issues, or degrading performance under load",
                        expected_impact="Stable error rates during extended usage",
                        implementation_difficulty="high"
                    )
                    recommendations.append(recommendation)
        
        return recommendations
    
    def generate_scaling_insights(self, concurrency_analysis: Dict) -> List[Insight]:
        """Generate insights on scaling behavior and capacity limits.
        
        Args:
            concurrency_analysis: Dictionary containing concurrency analysis results
            
        Returns:
            List of Insight objects
        """
        insights = []
        
        correlation = concurrency_analysis.get("correlation", 0)
        has_degradation = concurrency_analysis.get("has_degradation", False)
        degradation_threshold = concurrency_analysis.get("degradation_threshold", 0)
        
        # Generate insights based on correlation
        if correlation > 0.8:
            insight = Insight(
                topic="Strong Correlation with Concurrency",
                description="There is a strong correlation between the number of concurrent users and response times, indicating potential scalability issues",
                supporting_data={"correlation": correlation}
            )
            insights.append(insight)
        elif correlation > 0.5:
            insight = Insight(
                topic="Moderate Correlation with Concurrency",
                description="There is a moderate correlation between the number of concurrent users and response times, suggesting some scalability concerns",
                supporting_data={"correlation": correlation}
            )
            insights.append(insight)
        elif correlation < 0.2 and correlation > -0.2:
            insight = Insight(
                topic="No Correlation with Concurrency",
                description="There is little to no correlation between the number of concurrent users and response times, suggesting good scalability",
                supporting_data={"correlation": correlation}
            )
            insights.append(insight)
        
        # Generate insights based on degradation threshold
        if has_degradation:
            insight = Insight(
                topic="Performance Degradation Threshold",
                description=f"Performance begins to degrade significantly at {degradation_threshold} concurrent users, indicating a potential capacity limit",
                supporting_data={"degradation_threshold": degradation_threshold}
            )
            insights.append(insight)
            
            # Add recommendation for addressing the degradation
            if degradation_threshold > 0:
                insight = Insight(
                    topic="Scaling Recommendation",
                    description=f"Consider horizontal scaling or optimization before reaching {degradation_threshold} concurrent users to maintain performance",
                    supporting_data={"degradation_threshold": degradation_threshold}
                )
                insights.append(insight)
        else:
            insight = Insight(
                topic="No Performance Degradation Detected",
                description="No significant performance degradation was detected with increasing concurrent users within the tested range",
                supporting_data={}
            )
            insights.append(insight)
        
        return insights
    
    def prioritize_recommendations(self, recommendations: List[Recommendation]) -> List[Dict]:
        """Prioritize recommendations based on potential impact.
        
        Args:
            recommendations: List of Recommendation objects
            
        Returns:
            List of dictionaries containing prioritized recommendations
        """
        if not recommendations:
            return []
        
        # Define scoring system
        severity_scores = {
            "high": 3,
            "medium": 2,
            "low": 1
        }
        
        difficulty_scores = {
            "low": 3,
            "medium": 2,
            "high": 1
        }
        
        # Calculate priority score for each recommendation
        prioritized = []
        for recommendation in recommendations:
            # Extract severity from the issue (if available)
            severity = "medium"  # Default
            if "critical" in recommendation.issue.lower():
                severity = "high"
            elif "moderate" in recommendation.issue.lower():
                severity = "medium"
            elif "minor" in recommendation.issue.lower():
                severity = "low"
            
            # Get difficulty
            difficulty = recommendation.implementation_difficulty
            
            # Calculate priority score (higher is more important)
            severity_score = severity_scores.get(severity, 2)
            difficulty_score = difficulty_scores.get(difficulty, 2)
            
            # Priority formula: severity * 2 + ease of implementation
            # This weights severity more heavily than implementation difficulty
            priority_score = severity_score * 2 + difficulty_score
            
            prioritized.append({
                "recommendation": recommendation,
                "priority_score": priority_score,
                "priority_level": self._get_priority_level(priority_score)
            })
        
        # Sort by priority score (descending)
        prioritized.sort(key=lambda x: x["priority_score"], reverse=True)
        
        return prioritized
    
    def _get_priority_level(self, score: int) -> str:
        """Convert a priority score to a priority level.
        
        Args:
            score: Priority score
            
        Returns:
            Priority level string
        """
        if score >= 7:
            return "critical"
        elif score >= 5:
            return "high"
        elif score >= 3:
            return "medium"
        else:
            return "low"