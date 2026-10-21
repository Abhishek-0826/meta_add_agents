import java.util.*;
class Demo{
    public static void main(String [] args){
        Scanner sc = new Scanner(System.in);
        int n = sc.nextInt();
        int a = 1;

        for(int i = n ; i > 0 ; i--){
            for(int j = 1 ; j <= n ; j++){
                if(j < i){
                    System.out.print("  ");
                }else{
                     System.out.print(a+" ");
                     a++;
                }
            }
            a = 1;
            System.out.println();
        }
    }
}