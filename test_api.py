#!/usr/bin/env python3
"""
Test script to populate the rating system with sample data
"""

import requests
import random
from datetime import datetime, timedelta

API_URL = "http://localhost:8000"

# Sample feedback texts
positive_feedback = [
    "Excellent support, very helpful!",
    "Quick response and solved my issue perfectly",
    "Outstanding service, highly recommend",
    "Very professional and knowledgeable",
    "Great experience, thank you!"
]

neutral_feedback = [
    "Average experience, nothing special",
    "Got my issue resolved eventually",
    "Standard service, met expectations",
    "Okay, but could be better"
]

negative_feedback = [
    "Long wait time, not satisfied",
    "Issue not fully resolved",
    "Poor communication",
    "Unhelpful and frustrating experience",
    "Disappointed with the service"
]

def generate_sample_ratings(count=50):
    """Generate sample ratings with realistic distribution"""
    
    print(f"\n{'='*60}")
    print(f"Generating {count} sample ratings...")
    print(f"{'='*60}\n")
    
    success_count = 0
    
    for i in range(count):
        # Generate weighted random rating (more 4s and 5s)
        rating = random.choices(
            [1, 2, 3, 4, 5],
            weights=[5, 10, 15, 35, 35]  # Weighted towards higher ratings
        )[0]
        
        # Select appropriate feedback
        if rating >= 4:
            feedback = random.choice(positive_feedback)
        elif rating == 3:
            feedback = random.choice(neutral_feedback)
        else:
            feedback = random.choice(negative_feedback)
        
        # Create rating data
        rating_data = {
            "conversation_id": f"conv_{1000 + i}",
            "rating": rating,
            "feedback": feedback,
            "user_id": f"user_{random.randint(1, 100)}",
            "metadata": {
                "agent_id": f"agent_{random.randint(1, 20)}",
                "duration_seconds": random.randint(60, 600),
                "category": random.choice(["technical_support", "billing", "general_inquiry", "complaint"])
            }
        }
        
        try:
            response = requests.post(f"{API_URL}/ratings", json=rating_data)
            if response.status_code == 201:
                success_count += 1
                print(f"✓ Created rating {i+1}/{count}: {rating} stars - {feedback[:40]}...")
            else:
                print(f"✗ Failed to create rating {i+1}: {response.status_code}")
        except Exception as e:
            print(f"✗ Error creating rating {i+1}: {e}")
    
    print(f"\n{'='*60}")
    print(f"✓ Successfully created {success_count}/{count} ratings")
    print(f"{'='*60}\n")

def display_analytics():
    """Fetch and display analytics"""
    
    print(f"\n{'='*60}")
    print("📊 ANALYTICS SUMMARY")
    print(f"{'='*60}\n")
    
    try:
        # Get summary
        response = requests.get(f"{API_URL}/analytics/summary")
        summary = response.json()
        
        print(f"Total Ratings: {summary['total_ratings']}")
        print(f"Average Rating: {summary['average_rating']}/5.0")
        print("\nRating Distribution:")
        for star, count in summary['rating_distribution'].items():
            bar = "█" * int(count / 2)  # Simple bar chart
            print(f"  {star} star: {count:3d} {bar}")
        
        print("\nSentiment Breakdown:")
        for sentiment, count in summary['sentiment_breakdown'].items():
            print(f"  {sentiment.capitalize()}: {count}")
        
        # Get distribution with percentages
        print(f"\n{'='*60}")
        response = requests.get(f"{API_URL}/analytics/distribution")
        distribution = response.json()
        
        print("\nDetailed Distribution:")
        for star_level, data in distribution['distribution'].items():
            print(f"  {star_level}: {data['count']} ({data['percentage']}%)")
        
        # Get trends
        print(f"\n{'='*60}")
        response = requests.get(f"{API_URL}/analytics/trends?days=7")
        trends = response.json()
        
        print(f"\n7-Day Trends:")
        print(f"  Ratings in period: {trends['total_ratings']}")
        print(f"  Average rating: {trends['average_rating']}/5.0")
        print(f"  Trend: {trends['trend'].upper()}")
        
        print(f"\n{'='*60}\n")
        
    except Exception as e:
        print(f"Error fetching analytics: {e}")

def main():
    print("\n" + "="*60)
    print("🧪 Rating System Test Script")
    print("="*60)
    print("\nMake sure the API server is running (python app.py)")
    print("Press Enter to continue or Ctrl+C to cancel...")
    input()
    
    # Generate sample data
    generate_sample_ratings(50)
    
    # Display analytics
    display_analytics()
    
    print("\n✅ Test complete!")
    print("\nYou can now:")
    print("  1. View interactive docs: http://localhost:8000/docs")
    print("  2. Export data: curl 'http://localhost:8000/export?format=csv' -o ratings.csv")
    print("  3. View analytics: curl http://localhost:8000/analytics/summary")

if __name__ == "__main__":
    main()
