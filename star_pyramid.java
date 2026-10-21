import java.util.*;
class Demo{
    public static void main(String [] args){
        Scanner sc = new Scanner(System.in);
        int n = sc.nextInt();

        for(int i = 0 ; i < n ; i++){
            for (int s = 0; s < n - i - 1; s++) {
                System.out.print(" ");
            }
            for (int j = 0; j <= i; j++) {
                System.out.print("*");
                if (j < i){
                    System.out.print(" ");
                }
            }
            System.out.println();
        }
    }
}