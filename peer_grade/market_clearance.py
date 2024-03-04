from peer_course.models import *
from peer_assignment.models import *
import math



def reviews_to_sell(price, cid, independence=True):
    if price == 0:
        return 'Price can not be zero!'
    else:
        cms = CourseMember.objects.filter(
            course_id= cid,
            role ='student', 
            qualified = True, 
            is_independent= independence,
            active= True
                ).order_by("regular_points")
        num_to_sell= 0
        student_list=[]
        if cms.exists():
            for cm in cms:
                cm_num_to_sell= math.floor(cm.regular_points/price)
                student_list.append([cm, cm_num_to_sell])
                num_to_sell += math.floor(cm_num_to_sell)

        return num_to_sell, student_list


def sell_price(num_to_sell, cid, independence=True):
    price = 1
    sold, student_list = reviews_to_sell(1, cid, independence)

    while num_to_sell < reviews_to_sell(price, cid, independence)[0]:
        sold, student_list = reviews_to_sell(price, cid, independence)
        print(sold, student_list, price)
        price += 1

    num_final_sold, student_final_list = reviews_to_sell(price, cid, independence)
    if num_to_sell == num_final_sold:
        return price, num_final_sold, student_final_list
    else:
        if  price-1 ==0:
            return 0,0,0
        else:
            num_final_sold, student_final_list = reviews_to_sell(price-1, cid, independence) 
            return  price-1, num_final_sold, student_final_list

    
def calculation_review_reduction(aid, num_reviews_per_assignment, max_num_reviews_per_student, independence= True):
    assignment = Assignment.objects.get(id=aid)
    cid = assignment.course.id

    num_required_peer_reviews = num_reviews_per_assignment * AssignmentSubmission.objects.filter(
        assignment = assignment, calibration_id=0, 
        author__is_independent = independence
        ).count()

    num_available_reviews = max_num_reviews_per_student * CourseMember.objects.filter(
        course_id= cid,
        role ='student', 
        qualified = True, 
        is_independent= independence,
        active= True
            ).count()

    num_to_sell= num_available_reviews - num_required_peer_reviews

    price, num_potential_sold, student_final_list= sell_price(
        num_to_sell, cid, independence=independence)
    if price == 0:
        return 'Supply does not meet demand even with price of 0!'

    student_dict = dict(student_final_list)
    student_dict = dict.fromkeys(student_dict, 0)

    if num_potential_sold < num_to_sell:
        return 'Supply does not meet demand!'
    else:
        num_sold = 0
        while not num_sold == num_to_sell:
            for student,_ in student_final_list:
                if student.regular_points > price:
                    student.regular_points -= price
                    student.save()
                    num_sold +=1
                    student_dict[student] +=1
        return student_dict, price, num_sold

   
                    



    